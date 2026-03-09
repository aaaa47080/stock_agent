@echo off
chcp 65001 >nul
echo ============================================================
	echo    STOCK AGENT 測試計劃
echo ============================================================
echo.

:menu
echo 請選擇測試模式:
echo.
echo   [1] 自動測試-10 題 (約 3-5 分鐘)
echo   [2] 自動測試-30 題 (約 10-15 分鐘)
echo   [3] 互動式測試 (手動輸入問題)
echo   [4] 全部執行(10+30 題)
echo   [Q] 離開
echo.
set /p choice="請輸入選項: "

if /i "%choice%"=="1" goto test10
if /i "%choice%"=="2" goto test30
if /i "%choice%"=="3" goto interactive
if /i "%choice%"=="4" goto all
if /i "%choice%"=="Q" goto end
goto menu

:test10
echo.
echo [執行 10 題自動測試...]
echo ---
python tests/test_10_questions.py
echo.
pause
goto menu

:test30
echo.
echo [執行 30 題自動測試...]
echo ---
python tests/test_extended.py
echo.
pause
	goto menu

:interactive
echo.
echo [啟動互動式測試...]
echo [輸入 quit 或 exit 結束]
echo ---
python tests/test_interactive_user.py
goto menu

:all
echo.
echo [執行全部測試...]
	echo ===第一部分: 10 題 ===
python tests/test_10_questions.py
echo.
	echo === 第二部分: 30 題 ===
python tests/test_extended.py
echo.
echo 全部測試完成！
pause
goto menu

:end
echo 再見！
