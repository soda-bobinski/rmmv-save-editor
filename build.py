import PyInstaller.__main__
import os
import shutil

if os.path.exists('dist'):
    shutil.rmtree('dist')
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('RPGMakerSaveEditor.spec'):
    os.remove('RPGMakerSaveEditor.spec')

# Run PyInstaller
PyInstaller.__main__.run([
    'main.py',
    '--name=RPGMakerSaveEditor',
    '--onefile',
    '--windowed',
    '--icon=resources/icons/branding/icon.ico',
    '--add-data=styles;styles',
    '--add-data=resources;resources',
    '--hidden-import=lzstring',
    '--hidden-import=PySide6.QtSvg',
])