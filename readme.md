# A small program to sort images
- Start the program
- Click Settings button
- Choose Source / Target Folders
- Click "Start Sorting"

You can choose between "Don't Keep, Skip or Keep - also possible via Keybinds.
The Program will read the images you want to keep, and make a copy in the target directory.

Happy Sorting!

# Build exe

```
pyinstaller --onefile --windowed --icon=assets/logo/icon.ico
--name="ImageSorter" --add-data="assets/logo/icon.ico;assets/logo" --optimize=2 app.py
```
