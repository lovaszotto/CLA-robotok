import subprocess
from robot.api import logger

def RunRealtimeToLog(cmd, log_file, cwd=None):
    # Log file megnyitása append módban
    with open(log_file, "a", encoding="utf-8") as log:
        
        # Process indítása
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Soronkénti olvasás és logolás
        for line in process.stdout:
            clean = line.rstrip("\n")
            # Próbáljuk explicit módon UTF-8-ra konvertálni (ha valami miatt nem string)
            try:
                clean_utf8 = clean.encode('utf-8', errors='replace').decode('utf-8') if not isinstance(clean, str) else clean
            except Exception:
                clean_utf8 = clean

            # Konzolra (futás közben látható)
            logger.console(clean_utf8)

            # Robot logba
            logger.info(clean_utf8)

            # Log file-ba
            log.write(clean_utf8 + "\n")
            log.flush()

        # Process lezárása
        process.wait()
        return process.returncode
