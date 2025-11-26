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

            # Konzolra (futás közben látható)
            logger.console(clean)

            # Robot logba
            logger.info(clean)

            # Log file-ba
            log.write(clean + "\n")
            log.flush()

        # Process lezárása
        process.wait()
        return process.returncode
