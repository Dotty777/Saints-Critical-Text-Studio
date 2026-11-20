' Windowless Native Desktop Launcher for Saints Critical Text Studio
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir
shell.Run "pythonw.exe """ & appDir & "\app.py""", 0, False
