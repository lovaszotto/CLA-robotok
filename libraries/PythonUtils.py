"""
PythonUtils library a Robot Framework számára
Dinamikus Python executable meghatározás és egyéb Python kapcsolódó műveletek
"""

import os
import sys
import platform
from pathlib import Path


class PythonUtils:
    """Robot Framework library Python executable dinamikus meghatározásához."""
    
    def get_python_executable(self):
        """Meghatározza a megfelelő Python executable útvonalát.
        
        Prioritási sorrend:
        1. Virtuális környezet (rf_env/Scripts/python.exe vagy rf_env/bin/python)
        2. Aktuális Python interpreter (sys.executable)
        3. Rendszer PATH-ban található python
        
        Returns:
            str: A Python executable teljes útvonala
        """
        # 1. Virtuális környezet ellenőrzése
        current_dir = os.getcwd()
        
        # Windows virtuális környezet
        if platform.system() == "Windows":
            venv_python = os.path.join(current_dir, 'rf_env', 'Scripts', 'python.exe')
        else:
            # Linux/Mac virtuális környezet
            venv_python = os.path.join(current_dir, 'rf_env', 'bin', 'python')
        
        if os.path.exists(venv_python):
            return os.path.abspath(venv_python)
        
        # 2. Aktuális Python interpreter
        if sys.executable:
            return sys.executable
        
        # 3. Fallback - rendszer python
        return 'python'
    
    def get_python_version(self, python_executable=None):
        """Visszaadja a Python verzióját.
        
        Args:
            python_executable (str, optional): Python executable útvonala. 
                                             Ha nincs megadva, a get_python_executable() eredményét használja.
        
        Returns:
            str: Python verzió (pl. "3.11.4")
        """
        if not python_executable:
            python_executable = self.get_python_executable()
        
        try:
            import subprocess
            result = subprocess.run([python_executable, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Kimenet: "Python 3.11.4"
                return result.stdout.strip().split()[-1]
            return "Ismeretlen"
        except Exception as e:
            return f"Hiba: {str(e)}"
    
    def check_python_executable_exists(self, python_executable=None):
        """Ellenőrzi, hogy a Python executable létezik és futtatható-e.
        
        Args:
            python_executable (str, optional): Python executable útvonala.
        
        Returns:
            bool: True, ha a Python executable elérhető
        """
        if not python_executable:
            python_executable = self.get_python_executable()
        
        try:
            import subprocess
            result = subprocess.run([python_executable, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_working_directory(self):
        """Visszaadja az aktuális munkakönyvtárat.
        
        Returns:
            str: Aktuális munkakönyvtár
        """
        return os.getcwd()
    
    def get_virtual_env_path(self):
        """Visszaadja a virtuális környezet útvonalát, ha létezik.
        
        Returns:
            str: Virtuális környezet útvonala vagy üres string
        """
        current_dir = os.getcwd()
        
        if platform.system() == "Windows":
            venv_path = os.path.join(current_dir, 'rf_env', 'Scripts')
        else:
            venv_path = os.path.join(current_dir, 'rf_env', 'bin')
        
        if os.path.exists(venv_path):
            return os.path.abspath(venv_path)
        
        return ""


# Robot Framework keyword aliases
get_python_executable = PythonUtils().get_python_executable
get_python_version = PythonUtils().get_python_version
check_python_executable_exists = PythonUtils().check_python_executable_exists
get_working_directory = PythonUtils().get_working_directory
get_virtual_env_path = PythonUtils().get_virtual_env_path