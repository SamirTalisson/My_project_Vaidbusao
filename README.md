# VaidBusão

## Descrição do projeto

VaidBusão é um sistema de controle de embarque para transporte escolar e universitário, desenvolvido em Python com a biblioteca Flet. A aplicação permite gerenciar usuários, veículos, listas de passageiros, relatórios de reabertura e alternar entre modo claro e escuro, tudo com persistência em banco de dados SQLite.

## Tecnologias utilizadas

- Python 3.14
- Flet
- SQLite
- JSON para configuração de temas
- Biblioteca padrão do Python para manipulação de arquivos e datas

## Requisitos para execução

- Python 3.14 instalado no sistema
- A biblioteca flet instalada
- Acesso de gravação na pasta do projeto para criação do banco de dados e do arquivo settings.json
- Atentesse às imagens, baixe ambas para que o aplicativo funcione normalmente

## Passo a passo para instalação

1. Abra um terminal na pasta do projeto VaidBusão.
2. Crie e ative um ambiente virtual (opcional, mas recomendado):
   - Windows:
     powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     
   - Linux/macOS:
     bash
     python3 -m venv venv
     source venv/bin/activate
     
3. Instale a dependência do Flet:
   bash
   python -m pip install flet
   

## Passo a passo para execução

1. Certifique-se de estar na pasta do projeto VaidBusão.
2. Execute o arquivo principal:
   bash
   python Vaidbusao.py
   
3. O aplicativo será iniciado no modo gráfico pelo Flet.
4. Use o usuário padrão criado automaticamente para login, se necessário:
   - Nome: Samir
   - Email: sam@gmail.com
   - Senha: 123

## Observações
- O sistema cria automaticamente os bancos de dados necessários na primeira execução.
- O tema selecionado é salvo em settings.json para ser mantido entre execuções.
- O sistema cria automaticamente os bancos de dados necessários na primeira execução.
- O tema selecionado é salvo em settings.json para ser mantido entre execuções.
