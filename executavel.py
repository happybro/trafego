"""Ponto de entrada para empacotar o JV Ads com PyInstaller.

Um arquivo simples na raiz facilita o empacotamento em um executavel
unico. Para o uso normal, prefira `python -m jv_ads` ou os lancadores
(iniciar.bat / iniciar.sh).
"""
from jv_ads.main import run

if __name__ == "__main__":
    run()
