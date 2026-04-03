@echo off
setlocal

if not exist "C:\bstk" mkdir "C:\bstk" >nul 2>&1

set "HOME=C:\Users\lpaiu"
set "VBOX_USER_HOME=C:\ProgramData\BlueStacks_nxt\Engine\Manager"
set "VBOX_APP_HOME=C:\ProgramData\BlueStacks_nxt"
set "TEMP=C:\bstk"
set "TMP=C:\bstk"

(
  echo [%date% %time%] args=%*
  echo   HOME=%HOME%
  echo   VBOX_USER_HOME=%VBOX_USER_HOME%
  echo   VBOX_APP_HOME=%VBOX_APP_HOME%
  echo   TEMP=%TEMP%
  echo   TMP=%TMP%
) >> "C:\bstk\bstk-wrapper.log"

"C:\vs\other\arelwars\$root\PF\BstkSVC.exe" %*
