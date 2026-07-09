"""Gera o refresh token do Google Ads (executar uma única vez).

Pré-requisitos (veja o README para o passo a passo):
  1. Developer token do Google Ads (Centro de API da conta de administrador).
  2. Cliente OAuth "App para computador" no Google Cloud Console
     (client_id e client_secret).

Uso:
    python setup_oauth.py

O script abre o navegador para você autorizar o acesso e imprime o
refresh_token para colar no google-ads.yaml.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main() -> None:
    print("=== JV Ads — Configuração OAuth ===\n")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent")

    print("\n=== Sucesso! ===")
    print("Copie o valor abaixo para o campo refresh_token do google-ads.yaml:\n")
    print(f"  refresh_token: {creds.refresh_token}\n")
    print("IMPORTANTE: guarde este valor em segredo. Ele dá acesso à sua conta.")


if __name__ == "__main__":
    main()
