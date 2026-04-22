"""
Configuración global de pytest.
Agrega el directorio raíz al PYTHONPATH para que los imports funcionen
sin necesidad de instalar el paquete en modo editable.
"""
import os
import sys

# Agrega la raíz del proyecto al path de Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
