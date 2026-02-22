# School Basic Project

## Installation Instructions
1. Download the project archive and unpack the `.zip` package.
2. Navigate to the project folder and open your console or terminal in that directory.
3. Execute the following command to start the server:
   ```bash
   ./venv/Scripts/python.exe server.py
   ```
4. Now that the server is running, you can test everything at: http://localhost:8080

## If something get wrong
1. Install Python v3.13, you can use `winget`, the Microsoft Store, or download the installer directly from the [official Python website](https://www.python.org/downloads).
2. Close all of the consoles on you PC (to reload `PATH`)
3. Open console in the same directory as `server.py`
4. Execute the command below:
   ```bash
   python -m venv venv && .\venv\Scripts\pip.exe install -r req.txt && .\venv\Scripts\python.exe server.py
   ```

After this, I'm pretty sure that the server will work