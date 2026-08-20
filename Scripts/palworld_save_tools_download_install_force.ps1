Invoke-WebRequest -Uri "https://github.com/cheahjs/palworld-save-tools/archive/refs/heads/main.zip" -OutFile "main.zip"
Expand-Archive -Path "main.zip" -DestinationPath "temp_pws" -Force
Copy-Item -Path "temp_pws\palworld-save-tools-main\palworld_save_tools" -Destination ".\" -Recurse -Force
Remove-Item -Path "temp_pws" -Recurse -Force
Remove-Item -Path "main.zip" -Force