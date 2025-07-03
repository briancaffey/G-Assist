# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

''' RISE plugin template code.

The following code can be used to create a RISE plugin written in Python. RISE
plugins are Windows based executables. They are spawned by the RISE plugin
manager. Communication between the plugin and the manager are done via pipes.
'''
import json
import logging
import os
import random
import tempfile
import requests
from ctypes import byref, windll, wintypes
from typing import Optional
from PIL import Image


from typing import TypedDict

class Response(TypedDict, total=False):
    success: bool
    message: Optional[str]


LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'flux_plugin.log')
BASE_SCREENSHOT_DIRECTORY = os.path.join("E:\\", 'Videos', 'NVIDIA')
CONFIG_FILE = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    r'NVIDIA Corporation\nvtopps\rise\plugins\flux',
    'config.json'
)
GAME_DIRECTORY = None
NVIDIA_API_KEY = None
OUTPUT_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'g-assist-plugin-flux')

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    ''' Main entry point.

    Sits in a loop listening to a pipe, waiting for commands to be issued. After
    receiving the command, it is processed and the result returned. The loop
    continues until the "shutdown" command is issued.

    Returns:
        0 if no errors occurred during execution; non-zero if an error occurred
    '''
    # Add startup logging to help debug
    try:
        logging.info('=== Flux Plugin Starting ===')
        logging.info(f'Log file location: {LOG_FILE}')
        logging.info(f'Base screenshot directory: {BASE_SCREENSHOT_DIRECTORY}')
        logging.info(f'Config file location: {CONFIG_FILE}')
    except Exception as e:
        # If logging fails, try to write to a simple file
        try:
            with open(os.path.join(os.environ.get("USERPROFILE", "."), 'flux_plugin_error.log'), 'a') as f:
                f.write(f'{__import__("datetime").datetime.now()} - Failed to start logging: {str(e)}\n')
        except:
            pass
        return 1

    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'messages'
    SYSTEM_INFO_PROPERTY = 'system_info'  # Added for game information
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'properties'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'


    ERROR_MESSAGE = 'Plugin Error!'

    # Generate command handler mapping
    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'set_random_color_wallpaper': execute_set_random_color_wallpaper_command,
        'set_color_wallpaper': execute_set_color_wallpaper_command,
        'set_latest_screenshot_as_wallpaper': execute_set_latest_screenshot_as_wallpaper_command,
        'generate_flux_image': execute_generate_flux_image_command,
    }
    cmd = ''

    logging.info('Flux Plugin started')
    logging.info(f'Available commands: {list(commands.keys())}')
    while cmd != SHUTDOWN_COMMAND:
        response = None
        input = read_command()
        if input is None:
            logging.error('Error reading command')
            continue

        logging.info(f'Received input: {input}')
        
        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logging.info(f'Processing command: {cmd}')
                    if cmd in commands:
                        if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                            response = commands[cmd]()
                        else:
                            response = execute_initialize_command()
                            # Get parameters from the tool_call, not from input root
                            params = tool_call.get('params', {}) if 'params' in tool_call else {}
                            context = input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None
                            system_info = input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None
                            
                            logging.info(f'Calling {cmd} with params: {params}, context: {context}, system_info: {system_info}')
                            response = commands[cmd](params, context, system_info)
                    else:
                        logging.warning(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                else:
                    logging.warning('Malformed input: missing function property')
                    response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
        else:
            logging.warning('Malformed input: missing tool_calls property')
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        logging.info(f'Sending response: {response}')
        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            logging.info('Shutdown command received, terminating plugin')
            break
    
    logging.info('Flux Plugin stopped.')
    return 0


def read_command() -> dict | None:
    ''' Reads a command from the communication pipe.

    Returns:
        Command details if the input was proper JSON; `None` otherwise
    '''
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
        chunks = []

        while True:
            BUFFER_SIZE = 4096
            message_bytes = wintypes.DWORD()
            buffer = bytes(BUFFER_SIZE)
            success = windll.kernel32.ReadFile(
                pipe,
                buffer,
                BUFFER_SIZE,
                byref(message_bytes),
                None
            )

            if not success:
                logging.error('Error reading from command pipe')
                return None

            # Add the chunk we read
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            # If we read less than the buffer size, we're done
            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        return json.loads(retval)

    except json.JSONDecodeError:
        logging.error('Failed to decode JSON input')
        return None
    except Exception as e:
        logging.error(f'Unexpected error in read_command: {str(e)}')
        return None


def write_response(response:Response) -> None:
    ''' Writes a response to the communication pipe.

    Args:
        response: Function response
    '''
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)

        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            byref(bytes_written),
            None
        )

    except Exception as e:
        logging.error(f'Failed to write response: {str(e)}')
        pass


def generate_failure_response(message:str=None) -> Response:
    ''' Generates a response indicating failure.

    Parameters:
        message: String to be returned in the response (optional)

    Returns:
        A failure response with the attached message
    '''
    response = { 'success': False }
    if message:
        response['message'] = message
    return response


def generate_success_response(message:str=None) -> Response:
    ''' Generates a response indicating success.

    Parameters:
        message: String to be returned in the response (optional)

    Returns:
        A success response with the attached massage
    '''
    response = { 'success': True }
    if message:
        response['message'] = message
    return response


def find_latest_file(directory: str, extension: str) -> Optional[str]:
    ''' Finds the latest file with the specified extension in the given directory.
    
    Args:
        directory: Directory to search in
        extension: File extension to look for (e.g., '.png', '.jpg')
        
    Returns:
        Path to the latest file, or None if no files found
    '''
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(extension)]
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        logging.error(f'Error finding latest file: {str(e)}')
        return None


def generate_random_hex_color() -> str:
    ''' Generates a random hex color code.
    
    Returns:
        A random hex color code (e.g., '#FF5733')
    '''
    return f"#{random.randint(0, 255):02X}{random.randint(0, 255):02X}{random.randint(0, 255):02X}"


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    ''' Converts hex color to RGB tuple.
    
    Args:
        hex_color: Hex color code (e.g., '#FF5733' or 'FF5733')
        
    Returns:
        RGB tuple (r, g, b)
    '''
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')
    
    # Convert to RGB
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    return (r, g, b)


def create_color_image(color: str, width: int = 1920, height: int = 1080) -> str:
    ''' Creates a solid color image and saves it to a temporary file.
    
    Args:
        color: Hex color code
        width: Image width (default: 1920)
        height: Image height (default: 1080)
        
    Returns:
        Path to the created image file
    '''
    try:
        # Convert hex to RGB
        rgb_color = hex_to_rgb(color)
        
        # Create a new image with the specified color
        image = Image.new('RGB', (width, height), rgb_color)
        
        # Save to temporary file
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f'flux_wallpaper_{color.lstrip("#")}.png')
        
        image.save(temp_file, 'PNG')
        logging.info(f'Created color image: {temp_file}')
        
        return temp_file
        
    except Exception as e:
        logging.error(f'Error creating color image: {str(e)}')
        raise


def set_windows_wallpaper(image_path: str) -> bool:
    ''' Sets the Windows desktop wallpaper.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        True if successful, False otherwise
    '''
    try:
        # Convert path to absolute path
        abs_path = os.path.abspath(image_path)
        
        # Use Windows API to set wallpaper
        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        
        # Set the wallpaper
        result = windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER,
            0,
            abs_path,
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        
        if result:
            logging.info(f'Successfully set wallpaper to: {abs_path}')
            return True
        else:
            logging.error('Failed to set wallpaper')
            return False
            
    except Exception as e:
        logging.error(f'Error setting wallpaper: {str(e)}')
        return False


def execute_initialize_command() -> dict:
    ''' Command handler for `initialize` function

    This handler is responseible for initializing the plugin.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    global GAME_DIRECTORY, NVIDIA_API_KEY, OUTPUT_DIRECTORY
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            GAME_DIRECTORY = config.get('GAME_DIRECTORY', None)
            NVIDIA_API_KEY = config.get('NVIDIA_API_KEY', None)
            OUTPUT_DIRECTORY = config.get('OUTPUT_DIRECTORY', OUTPUT_DIRECTORY)
        logging.info('Config loaded successfully.')
        logging.info(f'Game directory: {GAME_DIRECTORY}')
        logging.info(f'Output directory: {OUTPUT_DIRECTORY}')
        logging.info(f'NVIDIA API key configured: {"Yes" if NVIDIA_API_KEY else "No"}')
        return generate_success_response('Flux plugin initialized successfully.')
    except FileNotFoundError:
        logging.error('Config file not found, creating sample config.')
        # Create directory if it doesn't exist
        config_dir = os.path.dirname(CONFIG_FILE)
        os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                "GAME_DIRECTORY": "GAME_DIRECTORY_HERE",
                "NVIDIA_API_KEY": "YOUR_NVIDIA_API_KEY_HERE",
                "OUTPUT_DIRECTORY": OUTPUT_DIRECTORY
            }, f, indent=4)
        return generate_failure_response('Config file not found. Sample config created.')
    except Exception as e:
        logging.error(f'Error loading config: {str(e)}')
        return generate_failure_response('Failed to initialize.')


def execute_shutdown_command() -> dict:
    ''' Command handler for `shutdown` function

    This handler is responsible for releasing any resources the plugin may have
    acquired during its operation (memory, access to hardware, etc.).

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info('Shutting down Flux plugin')
    # shutdown function body
    return generate_success_response('Flux plugin shutdown successfully.')


def execute_set_random_color_wallpaper_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `set_random_color_wallpaper` function

    Sets a random color as the Windows desktop wallpaper.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info('Executing set_random_color_wallpaper')
    
    try:
        # Generate a random color
        random_color = generate_random_hex_color()
        logging.info(f'Generated random color: {random_color}')
        
        # Create an image with the random color
        image_path = create_color_image(random_color)
        
        # Set the wallpaper
        success = set_windows_wallpaper(image_path)
        
        if success:
            return generate_success_response(f'Successfully set wallpaper to random color: {random_color}')
        else:
            return generate_failure_response('Failed to set wallpaper')
            
    except Exception as e:
        logging.error(f'Error in set_random_color_wallpaper: {str(e)}')
        return generate_failure_response(f'Error setting random color wallpaper: {str(e)}')


def execute_set_color_wallpaper_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `set_color_wallpaper` function

    Sets a specific color as the Windows desktop wallpaper.

    Args:
        params: Function parameters containing the color
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing set_color_wallpaper with params: {params}')
    
    try:
        # Get color from parameters
        if not params or 'color' not in params:
            return generate_failure_response('No color specified. Please provide a hex color code.')
        
        color = params['color']
        
        # Validate color format
        if not color.startswith('#') and len(color) == 6:
            color = '#' + color
        elif not color.startswith('#') or len(color) != 7:
            return generate_failure_response('Invalid color format. Please use hex format (e.g., "#FF5733" or "FF5733")')
        
        logging.info(f'Setting wallpaper to color: {color}')
        
        # Create an image with the specified color
        image_path = create_color_image(color)
        
        # Set the wallpaper
        success = set_windows_wallpaper(image_path)
        
        if success:
            return generate_success_response(f'Successfully set wallpaper to color: {color}')
        else:
            return generate_failure_response('Failed to set wallpaper')
            
    except Exception as e:
        logging.error(f'Error in set_color_wallpaper: {str(e)}')
        return generate_failure_response(f'Error setting color wallpaper: {str(e)}')


def execute_set_latest_screenshot_as_wallpaper_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `set_latest_screenshot_as_wallpaper` function

    Sets the latest screenshot as the Windows desktop wallpaper.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info('Executing set_latest_screenshot_as_wallpaper')
    
    try:
        # Determine screenshot directory - use game-specific directory if available
        global GAME_DIRECTORY
        if GAME_DIRECTORY:
            screenshot_directory = os.path.join(BASE_SCREENSHOT_DIRECTORY, GAME_DIRECTORY)
        else:
            screenshot_directory = BASE_SCREENSHOT_DIRECTORY
        
        logging.info(f'Searching for screenshots in: {screenshot_directory}')
        
        # Find the latest screenshot file
        file_path = find_latest_file(screenshot_directory, '.png')
        
        if not file_path:
            # Try other image formats if PNG not found
            for ext in ['.jpg', '.jpeg']:
                file_path = find_latest_file(screenshot_directory, ext)
                if file_path:
                    break
        
        if not file_path:
            return generate_failure_response('No screenshot found.')
        
        logging.info(f'Found latest screenshot: {file_path}')
        
        # Set the wallpaper
        success = set_windows_wallpaper(file_path)
        
        if success:
            filename = os.path.basename(file_path)
            return generate_success_response(f'Successfully set wallpaper to latest screenshot: {filename}')
        else:
            return generate_failure_response('Failed to set wallpaper')
            
    except Exception as e:
        logging.error(f'Error in set_latest_screenshot_as_wallpaper: {str(e)}')
        return generate_failure_response(f'Error setting latest screenshot as wallpaper: {str(e)}')


def execute_generate_flux_image_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `generate_flux_image` function

    Generates an image using the Flux Dev NIM from NVIDIA.

    Args:
        params: Function parameters (optional prompt)
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info('Executing generate_flux_image')
    
    try:
        # Check if API key is configured
        global NVIDIA_API_KEY
        if not NVIDIA_API_KEY or NVIDIA_API_KEY == "YOUR_NVIDIA_API_KEY_HERE":
            return generate_failure_response('NVIDIA API key not configured. Please set NVIDIA_API_KEY in config.json')
        
        # Get prompt from parameters (optional)
        prompt = params.get('prompt', '') if params else ''
        if not prompt:
            prompt = "A beautiful landscape with mountains and a lake"
            logging.info(f'No prompt provided, using default: {prompt}')
        else:
            logging.info(f'Using provided prompt: {prompt}')
        
        # Ensure output directory exists
        global OUTPUT_DIRECTORY
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
        logging.info(f'Output directory: {OUTPUT_DIRECTORY}')
        
        # Prepare the API request
        url = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
        
        payload = {
            "height": 768,
            "width": 1344,
            "cfg_scale": 5,
            "mode": "base",
            "samples": 1,
            "seed": 0,
            "steps": 50,
            "prompt": prompt
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {NVIDIA_API_KEY}"
        }
        
        logging.info('Sending request to Flux NIM API...')
        logging.info(f'URL: {url}')
        logging.info(f'Payload: {payload}')
        
        # Make the API request
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        logging.info(f'Response status code: {response.status_code}')
        
        if response.status_code == 200:
            # Parse the response
            response_data = response.json()
            logging.info('Successfully received response from Flux NIM API')
            
            # Extract the image data from artifacts array
            if 'artifacts' in response_data and len(response_data['artifacts']) > 0:
                artifact = response_data['artifacts'][0]
                image_data = artifact['base64']
                
                # Generate filename with timestamp
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"flux_image_{timestamp}.png"
                file_path = os.path.join(OUTPUT_DIRECTORY, filename)
                
                # Save the image
                import base64
                image_bytes = base64.b64decode(image_data)
                
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                
                logging.info(f'Image saved successfully: {file_path}')
                
                return generate_success_response(f'Successfully generated Flux image: {filename}')
            else:
                logging.error('No artifacts found in API response')
                return generate_failure_response('No artifacts found in API response')
        else:
            logging.error(f'API request failed with status {response.status_code}: {response.text}')
            return generate_failure_response(f'API request failed: {response.status_code} - {response.text}')
            
    except requests.exceptions.Timeout:
        logging.error('API request timed out')
        return generate_failure_response('API request timed out')
    except requests.exceptions.RequestException as e:
        logging.error(f'Network error: {str(e)}')
        return generate_failure_response(f'Network error: {str(e)}')
    except Exception as e:
        logging.error(f'Error in generate_flux_image: {str(e)}')
        return generate_failure_response(f'Error generating Flux image: {str(e)}')


if __name__ == '__main__':
    main()
