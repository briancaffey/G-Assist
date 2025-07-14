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
import time
import urllib.request
import urllib.error
import subprocess
import threading
from ctypes import byref, windll, wintypes
from typing import Optional


# Data Types
type Response = dict[str, any]

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'python_plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global configuration variables
CONFIG_FILE = os.path.join(f'{os.environ.get("PROGRAMDATA", ".")}{r'\NVIDIA Corporation\nvtopps\rise\plugins\flux'}', 'config.json')
GAME_DIRECTORY = None
NVIDIA_API_KEY = None
NGC_API_KEY = None
HF_TOKEN = None
LOCAL_NIM_CACHE = None
OUTPUT_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), "flux_output")
FLUX_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"

def load_config():
    ''' Load configuration from config.json file '''
    global GAME_DIRECTORY, NVIDIA_API_KEY, NGC_API_KEY, HF_TOKEN, LOCAL_NIM_CACHE, OUTPUT_DIRECTORY, FLUX_URL
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            GAME_DIRECTORY = config.get('GAME_DIRECTORY', None)
            NVIDIA_API_KEY = config.get('NVIDIA_API_KEY', None)
            NGC_API_KEY = config.get('NGC_API_KEY', None)
            HF_TOKEN = config.get('HF_TOKEN', None)
            LOCAL_NIM_CACHE = config.get('LOCAL_NIM_CACHE', None)
            OUTPUT_DIRECTORY = config.get('OUTPUT_DIRECTORY', OUTPUT_DIRECTORY)
            FLUX_URL = config.get('FLUX_URL', "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev")
            logging.info('Configuration loaded successfully')
    except FileNotFoundError:
        logging.warning(f'Config file not found: {CONFIG_FILE}')
    except json.JSONDecodeError as e:
        logging.error(f'Error parsing config file: {e}')
    except Exception as e:
        logging.error(f'Error loading config: {e}')


def main():
    ''' Main entry point.

    Sits in a loop listening to a pipe, waiting for commands to be issued. After
    receiving the command, it is processed and the result returned. The loop
    continues until the "shutdown" command is issued.

    Returns:
        0 if no errors occurred during execution; non-zero if an error occurred
    '''
    # Load configuration on startup
    load_config()

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
        'test_function': test_function,
        'simple_test': simple_test,
        'check_nim_status': check_nim_status,
        'stop_nim': stop_nim,
        'start_nim': start_nim,
        'generate_image': generate_image
    }
    cmd = ''

    logging.info('Plugin started')
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
                            response = commands[cmd](
                                tool_call.get('params', None),
                                input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None,
                                input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None  # Pass system_info directly
                            )
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
    
    logging.info('G-Assist Plugin stopped.')
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

        retval = buffer.decode('utf-8')[:message_bytes.value]
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

        json_message = json.dumps(response) + "<<END>>"
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)

        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
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


def generate_progress_response(message:str=None, status:str="processing") -> Response:
    ''' Generates a progress response for partial updates.

    Parameters:
        message: Progress message to display
        status: Status indicator (processing, success, error)

    Returns:
        A progress response with the attached message and status
    '''
    response = { 
        'success': True,
        'message': message,
        'status': status
    }
    return response


def execute_initialize_command() -> dict:
    ''' Command handler for `initialize` function

    This handler is responseible for initializing the plugin.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info('Initializing plugin')
    # initialization function body
    return generate_success_response('initialize success.')


def execute_shutdown_command() -> dict:
    ''' Command handler for `shutdown` function

    This handler is responsible for releasing any resources the plugin may have
    acquired during its operation (memory, access to hardware, etc.).

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info('Shutting down plugin')
    # shutdown function body
    return generate_success_response('shutdown success.')


def test_function(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `test_function` function

    Tests health endpoints on localhost:8000.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing test_function with params: {params}')

    try:
        # Step 1: Test live endpoint
        logging.info('Testing /v1/health/live endpoint...')
        live_url = 'http://localhost:8000/v1/health/live'

        try:
            with urllib.request.urlopen(live_url, timeout=5) as response:
                live_status = response.getcode()
                logging.info(f'Live endpoint status: {live_status}')
                if live_status != 200:
                    return generate_failure_response(f'Live endpoint returned status {live_status}')
        except urllib.error.URLError as e:
            logging.error(f'Error accessing live endpoint: {e}')
            return generate_failure_response(f'Live endpoint error: {e}')
        except Exception as e:
            logging.error(f'Unexpected error with live endpoint: {e}')
            return generate_failure_response(f'Live endpoint error: {e}')

        # Step 2: Test ready endpoint
        logging.info('Testing /v1/health/ready endpoint...')
        ready_url = 'http://localhost:8000/v1/health/ready'

        try:
            with urllib.request.urlopen(ready_url, timeout=5) as response:
                ready_status = response.getcode()
                logging.info(f'Ready endpoint status: {ready_status}')
                if ready_status != 200:
                    return generate_failure_response(f'Ready endpoint returned status {ready_status}')
        except urllib.error.URLError as e:
            logging.error(f'Error accessing ready endpoint: {e}')
            return generate_failure_response(f'Ready endpoint error: {e}')
        except Exception as e:
            logging.error(f'Unexpected error with ready endpoint: {e}')
            return generate_failure_response(f'Ready endpoint error: {e}')

        # Step 3: Success response
        logging.info('Both health endpoints are working!')
        final_response = generate_success_response('Service is live and ready!')
        logging.info(f'Final response: {final_response}')
        return final_response

    except Exception as e:
        logging.error(f'Error in test_function: {str(e)}')
        return generate_failure_response(f'Error in test_function: {str(e)}')


def simple_test(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `simple_test` function

    Simple test function that doesn't use RISE API.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing simple_test with params: {params}')

    try:
        logging.info('Simple test function executed successfully')
        return generate_success_response('Simple test function works!')

    except Exception as e:
        logging.error(f'Error in simple_test: {str(e)}')
        return generate_failure_response(f'Error in simple_test: {str(e)}')


def check_nim_status(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `check_nim_status` function

    Checks the status of the flux NIM server using WSL and podman.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing check_nim_status with params: {params}')

    try:
        # Check if nim-server container is running using WSL and podman
        logging.info('Checking if nim-server container is running...')
        check_cmd = ['wsl', '-d', 'NVIDIA-Workbench', 'podman', 'ps', '--filter', 'name=nim-server', '--format', '{{.Names}}']

        try:
            result = subprocess.run(check_cmd, check=True, capture_output=True, text=True)
            container_names = result.stdout.strip()
            logging.info(f'Nim-server container names: {container_names}')

            if container_names:
                return generate_success_response(f'NIM server is running. Container: {container_names}')
            else:
                return generate_failure_response('NIM server is not running.')

        except subprocess.CalledProcessError as e:
            logging.error(f'Error checking NIM server status: {e}')
            return generate_failure_response(f'Error checking NIM server status: {e}')
        except FileNotFoundError:
            logging.error('WSL or podman command not found')
            return generate_failure_response('WSL or podman command not found')
        except Exception as e:
            logging.error(f'Unexpected error checking NIM server status: {e}')
            return generate_failure_response(f'Error checking NIM server status: {e}')

    except Exception as e:
        logging.error(f'Error in check_nim_status: {str(e)}')
        return generate_failure_response(f'Error in check_nim_status: {str(e)}')


def stop_nim(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `stop_nim` function

    Stops the flux NIM server using WSL and podman.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing stop_nim with params: {params}')

    try:
        # Stop the nim-server container using WSL and podman
        logging.info('Stopping nim-server container...')
        stop_cmd = ['wsl', '-d', 'NVIDIA-Workbench', 'podman', 'stop', 'nim-server']

        try:
            result = subprocess.run(stop_cmd, check=True, capture_output=True, text=True)
            logging.info(f'Nim-server stop result: {result.stdout.strip()}')

            return generate_success_response('NIM server stopped successfully.')

        except subprocess.CalledProcessError as e:
            logging.error(f'Error stopping NIM server: {e}')
            return generate_failure_response(f'Error stopping NIM server: {e}')
        except FileNotFoundError:
            logging.error('WSL or podman command not found')
            return generate_failure_response('WSL or podman command not found')
        except Exception as e:
            logging.error(f'Unexpected error stopping NIM server: {e}')
            return generate_failure_response(f'Error stopping NIM server: {e}')
        
    except Exception as e:
        logging.error(f'Error in stop_nim: {str(e)}')
        return generate_failure_response(f'Error in stop_nim: {str(e)}')


def start_nim(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `start_nim` function

    Starts the flux NIM server using WSL and podman with configuration from config.json.

    Args:
        params: Function parameters
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing start_nim with params: {params}')
    
    try:
        # Reload configuration to ensure we have the latest values
        load_config()
        
        # Check configuration requirements
        global NGC_API_KEY, HF_TOKEN, LOCAL_NIM_CACHE
        if not NGC_API_KEY or NGC_API_KEY == "YOUR_NGC_API_KEY_HERE":
            return generate_failure_response('NGC API key not configured. Please set NGC_API_KEY in config.json')
        
        if not HF_TOKEN or HF_TOKEN == "YOUR_HF_TOKEN_HERE":
            return generate_failure_response('HF Token not configured. Please set HF_TOKEN in config.json')
        
        if not LOCAL_NIM_CACHE or LOCAL_NIM_CACHE == "/path/to/your/nim/cache":
            return generate_failure_response('Local NIM cache path not configured. Please set LOCAL_NIM_CACHE in config.json')
        
        # Check if NIM server is already running
        logging.info('Checking if Flux NIM server is already running...')
        check_result = check_nim_status()
        if check_result.get('success', False):
            return generate_failure_response('Flux NIM server is already running.')
        
        # Build the podman command
        logging.info('Starting Flux NIM server...')
        podman_cmd = [
            'wsl', '-d', 'NVIDIA-Workbench',
            'podman', 'run', '-d', '--rm', '--name=nim-server',
            '--device', 'nvidia.com/gpu=all',
            '-e', f'NGC_API_KEY={NGC_API_KEY}',
            '-e', f'HF_TOKEN={HF_TOKEN}',
            '-p', '8000:8000',
            '-v', f'{LOCAL_NIM_CACHE}:/opt/nim/.cache/',
            'nvcr.io/nim/black-forest-labs/flux.1-dev:1.0.0'
        ]
        
        try:
            # Start the container in the background
            result = subprocess.run(podman_cmd, check=True, capture_output=True, text=True)
            logging.info(f'NIM server start result: {result.stdout.strip()}')
            
            return generate_success_response('NIM server started successfully.')
                
        except subprocess.CalledProcessError as e:
            logging.error(f'Error starting NIM server: {e}')
            return generate_failure_response(f'Error starting NIM server: {e}')
        except FileNotFoundError:
            logging.error('WSL or podman command not found')
            return generate_failure_response('WSL or podman command not found')
        except Exception as e:
            logging.error(f'Unexpected error starting NIM server: {e}')
            return generate_failure_response(f'Error starting NIM server: {e}')
        
    except Exception as e:
        logging.error(f'Error in start_nim: {str(e)}')
        return generate_failure_response(f'Error in start_nim: {str(e)}')


def generate_image_worker(prompt: str, output_dir: str, flux_url: str, nvidia_api_key: str):
    ''' Background worker function to generate image '''
    try:
        logging.info(f'Starting background image generation for prompt: {prompt}')
        
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
            "Authorization": f"Bearer {nvidia_api_key}"
        }
        
        logging.info(f'Sending request to Flux API: {flux_url}')
        logging.info(f'Payload: {payload}')
        
        # Convert payload to JSON
        json_payload = json.dumps(payload)
        
        # Create request
        req = urllib.request.Request(flux_url, data=json_payload.encode('utf-8'), headers=headers, method='POST')
        
        # Send request
        with urllib.request.urlopen(req, timeout=300) as response:  # Increased timeout to 5 minutes
            response_data = json.loads(response.read().decode('utf-8'))
            logging.info(f'Flux API response received.')
            
            if 'artifacts' in response_data and len(response_data['artifacts']) > 0:
                artifact = response_data['artifacts'][0]
                image_data = artifact['base64']

                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"flux_image_{timestamp}.png"
                file_path = os.path.join(output_dir, filename)

                # Save the image
                import base64
                image_bytes = base64.b64decode(image_data)
                
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                
                logging.info(f'Image saved successfully: {file_path}')
            else:
                logging.error('No artifacts found in response')
                
    except urllib.error.URLError as e:
        logging.error(f'Error making request to Flux API: {e}')
    except urllib.error.HTTPError as e:
        logging.error(f'HTTP error from Flux API: {e}')
    except json.JSONDecodeError as e:
        logging.error(f'Error parsing API response: {e}')
    except Exception as e:
        logging.error(f'Unexpected error during image generation: {e}')


def generate_image(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `generate_image` function

    Generates an image using the Flux NIM API in a background thread.

    Args:
        params: Function parameters (can include 'prompt')
        context: Context information
        system_info: System information

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing generate_image with params: {params}')
    
    try:
        # Reload configuration to ensure we have the latest values
        load_config()
        
        # Check if NVIDIA API key is configured
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
        
        global FLUX_URL
        
        # Start image generation in background thread
        thread = threading.Thread(
            target=generate_image_worker,
            args=(prompt, OUTPUT_DIRECTORY, FLUX_URL, NVIDIA_API_KEY),
            daemon=True
        )
        thread.start()
        
        logging.info(f'Started background image generation thread for prompt: {prompt}')
        return generate_success_response(f'Your image generation request is in progress! Prompt: "{prompt}"')
        
    except Exception as e:
        logging.error(f'Error in generate_image: {str(e)}')
        return generate_failure_response(f'Error in generate_image: {str(e)}')


if __name__ == '__main__':
    main()
