# Telegram Video Downloader

Interface gráfica (Tkinter) para baixar todos os vídeos de um canal do Telegram,
com progresso em tempo real, retomada de downloads incompletos e opção de pular
vídeos individualmente.

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

Você precisa de um `API_ID` e `API_HASH` do Telegram (gratuitos):

1. Acesse https://my.telegram.org e faça login com seu número.
2. Vá em **API Development Tools** e crie um app.
3. Copie o `api_id` e o `api_hash` gerados.

Depois, escolha uma das opções:

- **Pela interface (recomendado):** rode o programa, clique em **⚙ Configurações**
  e preencha os campos. Isso salva tudo em um arquivo `.env` local.
- **Manualmente:** copie `.env.example` para `.env` e edite os valores.

Nenhuma credencial fica no código-fonte — tudo é lido do `.env`.

## Uso

```bash
python tg_video_downloader_3_0_.pyw
```

Preencha/confira as configurações, clique em **▶ Iniciar Download**. Na primeira
execução o Telegram vai pedir código de login (e senha de 2FA, se você tiver).
Depois disso, uma sessão local (`SESSION`) fica salva para não pedir login de novo.

## ⚠️ Segurança

- O arquivo `.env` e o arquivo de sessão (`*.session`, `*.session-journal`) contêm
  credenciais e autenticação ativa da sua conta. **Nunca faça commit deles** — o
  `.gitignore` deste projeto já os exclui por padrão.
- Se algum desses arquivos já foi exposto publicamente, revogue a sessão em
  Telegram → Configurações → Privacidade e Segurança → Sessões Ativas, e gere um
  novo `API_HASH` se possível.

## Estrutura

```
.
├── tg_video_downloader_3_0_.pyw   # aplicação principal
├── .env.example                    # modelo de configuração
├── .env                             # sua configuração local (não versionado)
├── requirements.txt
└── README.md
```
