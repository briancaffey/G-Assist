# G-Assist Flux Plugin

Transform your desktop experience with G-Assist! This plugin lets you set custom colors as your Windows wallpaper using simple voice commands or the G-Assist interface. Whether you want a random color, a specific hue, your latest screenshot, or generate AI images with Flux NIM, managing your desktop background has never been easier.

## What Can It Do?
- Set random colors as your Windows wallpaper
- Set specific hex colors as your wallpaper
- Set your latest screenshot as wallpaper
- Generate AI images using NVIDIA's Flux NIM
- Seamlessly integrates with your G-Assist setup
- Easy to set up and configure
- Creates beautiful solid color wallpapers or uses your screenshots

## Before You Start
Make sure you have:
- Windows PC
- Python 3.x installed on your computer
- G-Assist installed on your system
- NVIDIA API key (for Flux NIM image generation)

## Installation Guide

### Step 1: Set Up Python Environment
Run our setup script to create a virtual environment and install dependencies:
```bash
setup.bat
```

### Step 2: Build the Plugin
```bash
build.bat
```
This will create a `dist\flux` folder containing all the required files for the plugin.

### Step 3: Install the Plugin
1. Copy the entire `dist\flux` folder to:
   ```
   %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\
   ```

💡 **Tip**: Make sure all G-Assist clients are closed when copying files!

## How to Use
Once installed, you can control your wallpaper through G-Assist. Try these commands:

### Random Color Wallpaper
- Set random color: `Hey Flux, set a random color to the background`
- Random wallpaper: `Hey Flux, change my wallpaper to a random color`

### Specific Color Wallpaper
- Set specific color: `Hey Flux, set the background to red`
- Hex color: `Hey Flux, set wallpaper to #FF5733`
- Color code: `Hey Flux, change background to 00FF00`

### Screenshot Wallpaper
- Latest screenshot: `Hey Flux, set my latest screenshot as wallpaper`
- Screenshot background: `Hey Flux, use my latest screenshot as background`

### AI Image Generation
- Generate image: `Hey Flux, generate an image of a sunset over mountains`
- AI wallpaper: `Hey Flux, create an image of a forest landscape`

## Available Functions
The plugin includes these main functions:
- `set_random_color_wallpaper`: Sets a random color as wallpaper
- `set_color_wallpaper`: Sets a specific hex color as wallpaper
- `set_latest_screenshot_as_wallpaper`: Sets the latest screenshot as wallpaper
- `generate_flux_image`: Generates AI images using Flux NIM

### Configuration
The plugin can be configured through a JSON file. Edit the config file at:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\flux\config.json
```

Example configuration:
```json
{
    "GAME_DIRECTORY": "YourGameName",
    "NVIDIA_API_KEY": "your_nvidia_api_key_here",
    "OUTPUT_DIRECTORY": "C:\\Users\\YourUsername\\g-assist-plugin-flux"
}
```

**Important**: Replace `your_nvidia_api_key_here` with your actual NVIDIA API key for Flux NIM functionality.

If no game directory is specified, the plugin will look in the base NVIDIA screenshot directory.
If no output directory is specified, images will be saved to `%USERPROFILE%\g-assist-plugin-flux\`.

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\flux_plugin.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **Plugin not working?** Verify all files are copied to the plugins folder and restart G-Assist
- **Wallpaper not changing?** Check the log file for error messages
- **Permission issues?** Make sure you're running G-Assist with appropriate permissions

## Developer Documentation

### Architecture Overview
The Flux plugin is implemented as a Python-based service that creates solid color images and sets them as Windows desktop wallpapers using the Windows API.

### Core Components

#### Command Handling
- `read_command()`: Reads JSON-formatted commands from G-Assist's input pipe
- `write_response()`: Sends JSON-formatted responses back to G-Assist

#### Wallpaper Functions
- `generate_random_hex_color()`: Creates a random hex color code
- `hex_to_rgb()`: Converts hex colors to RGB tuples
- `create_color_image()`: Creates a solid color image file
- `set_windows_wallpaper()`: Sets the Windows desktop wallpaper using Windows API

#### Available Commands

##### Random Color Wallpaper
- `execute_set_random_color_wallpaper_command()`: Sets a random color as wallpaper
  - Generates a random hex color
  - Creates an image with that color
  - Sets it as the desktop wallpaper

##### Specific Color Wallpaper
- `execute_set_color_wallpaper_command()`: Sets a specific color as wallpaper
  - Accepts hex color parameter (e.g., "#FF5733" or "FF5733")
  - Validates color format
  - Creates an image with the specified color
  - Sets it as the desktop wallpaper

##### Screenshot Wallpaper
- `execute_set_latest_screenshot_as_wallpaper_command()`: Sets the latest screenshot as wallpaper
  - Searches for the most recent screenshot in the configured directory
  - Supports PNG, JPG, and JPEG formats
  - Uses game-specific directory if configured
  - Sets the found screenshot as the desktop wallpaper

### Configuration
The plugin supports configuration through a JSON file located at:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\flux\config.json
```

Configuration options:
- `GAME_DIRECTORY`: Optional game-specific directory for screenshots

If no configuration file exists, the plugin will create a sample one on first run.

### Error Handling
- Invalid color formats are caught and reported
- Windows API errors are logged with details
- User-friendly error messages are returned
- Comprehensive logging for debugging

### Adding New Features
To add new features:
1. Add new command to the commands dictionary in `main()`
2. Implement corresponding execute function
3. Add proper error handling and logging
4. Update the manifest.json with new function definition
5. Test the feature thoroughly
6. Run the setup & build scripts
7. Install and test the updated plugin

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the Windows API for wallpaper management
- Uses Pillow (PIL) for image creation
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.