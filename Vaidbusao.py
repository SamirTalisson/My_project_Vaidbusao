import flet as ft
import sqlite3
import json
import os
import asyncio
from datetime import datetime, time

# bancos de dados e arquivo de configuração usados pelo app
DB_CADASTRO = "cadastro.db"
DB_ENTRADA = "entrada_passa.db"
settings_file = "settings.json"


def _column_exists(conn, table_name, column_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]
    return column_name in columns


def ensure_database_schema():
    # cria tabelas e adiciona colunas se necessário
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS passageiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL UNIQUE
        )
    """)

    if not _column_exists(conn, "passageiros", "is_admin"):
        cur.execute(
            "ALTER TABLE passageiros ADD COLUMN is_admin INTEGER DEFAULT 0")

    if not _column_exists(conn, "passageiros", "is_owner"):
        cur.execute(
            "ALTER TABLE passageiros ADD COLUMN is_owner INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            placa TEXT PRIMARY KEY,
            capacidade INTEGER NOT NULL,
            motorista TEXT NOT NULL,
            horarios TEXT NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lista_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            status TEXT NOT NULL DEFAULT 'aberta',
            fechamento_hora TEXT
        )
    """)
    # adicionar coluna de reabertura se não existir
    if not _column_exists(conn, "lista_config", "reabertura_hora"):
        try:
            cur.execute(
                "ALTER TABLE lista_config ADD COLUMN reabertura_hora TEXT")
        except sqlite3.OperationalError:
            pass

    # Configurações por veículo (permite fechar listas individuais)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lista_config_veiculo (
            veiculo_placa TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'aberta',
            fechamento_hora TEXT
        )
    """)
    # adicionar coluna de reabertura por veículo se não existir
    if not _column_exists(conn, "lista_config_veiculo", "reabertura_hora"):
        try:
            cur.execute(
                "ALTER TABLE lista_config_veiculo ADD COLUMN reabertura_hora TEXT")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS relatorios_reabertura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            veiculo_placa TEXT,
            motorista TEXT,
            data_hora TEXT NOT NULL,
            fechamento_hora TEXT,
            reabertura_hora TEXT,
            passageiros_json TEXT NOT NULL,
            total_passageiros INTEGER NOT NULL
        )
    """)

    if not _column_exists(conn, "relatorios_reabertura", "motorista"):
        try:
            cur.execute(
                "ALTER TABLE relatorios_reabertura ADD COLUMN motorista TEXT")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

    conn = sqlite3.connect(DB_ENTRADA)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entrada_passa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            veiculo_placa TEXT NOT NULL,
            ida_volta TEXT NOT NULL,
            UNIQUE(nome, veiculo_placa)
        )
    """)

    try:
        cur.execute(
            "ALTER TABLE entrada_passa ADD COLUMN veiculo_placa TEXT DEFAULT 'ABC-1234'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    garantir_samir_admin()
    ensure_default_veiculos()


def ensure_default_veiculos():
    # adiciona veículos padrão apenas uma vez
    default_veiculos = [
        {
            "placa": "ABC-1234",
            "capacidade": 40,
            "motorista": "Caio",
            "horarios": [
                {"hora": "08:00", "ponto": "Centro", "tempo_ponto": "5 min"},
                {"hora": "14:00", "ponto": "Universidade", "tempo_ponto": "7 min"},
                {"hora": "19:00", "ponto": "Terminal", "tempo_ponto": "10 min"},
            ],
        },
        {
            "placa": "DEF-5678",
            "capacidade": 50,
            "motorista": "Jorge",
            "horarios": [
                {"hora": "09:00", "ponto": "Praça", "tempo_ponto": "6 min"},
                {"hora": "15:00", "ponto": "Shopping", "tempo_ponto": "8 min"},
                {"hora": "20:00", "ponto": "Terminal", "tempo_ponto": "10 min"},
            ],
        },
        {
            "placa": "GHI-9012",
            "capacidade": 35,
            "motorista": "Robson",
            "horarios": [
                {"hora": "07:30", "ponto": "Hospital", "tempo_ponto": "4 min"},
                {"hora": "13:30", "ponto": "Escola", "tempo_ponto": "6 min"},
                {"hora": "18:30", "ponto": "Terminal", "tempo_ponto": "8 min"},
            ],
        },
    ]

    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM veiculos")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    for veiculo in default_veiculos:
        cur.execute(
            "INSERT INTO veiculos (placa, capacidade, motorista, horarios, ativo) VALUES (?, ?, ?, ?, 1)",
            (
                veiculo["placa"],
                veiculo["capacidade"],
                veiculo["motorista"],
                json.dumps(veiculo["horarios"], ensure_ascii=False),
            ),
        )

    conn.commit()
    conn.close()


def cadastro_passageiro(nome, email, senha):
    try:
        conn = sqlite3.connect(DB_CADASTRO)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO passageiros (nome, email, senha, is_admin, is_owner) VALUES (?, ?, ?, 0, 0)",
            (nome, email, senha),
        )
        conn.commit()
        conn.close()
        return True, "Seu cadastro foi realizado com sucesso!"

    except sqlite3.IntegrityError:
        conn.close()
        return False, "Erro 350: Este e-mail já está cadastrado."


def fazer_login(email, senha):
    conn_login = sqlite3.connect(DB_CADASTRO)
    cur_login = conn_login.cursor()
    cur_login.execute(
        "SELECT id, nome, email, senha, is_admin, is_owner FROM passageiros WHERE email = ? AND senha = ?",
        (email, senha),
    )
    usuario = cur_login.fetchone()
    conn_login.close()

    if usuario:
        return True, "Login realizado com sucesso!", usuario
    return False, "E-mail ou senha incorretos! Tente novamente.", None


def definir_admin(nome_ou_email, tornar_admin=True):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "UPDATE passageiros SET is_admin = ? WHERE nome = ? OR email = ?",
        (1 if tornar_admin else 0, nome_ou_email, nome_ou_email),
    )
    conn.commit()
    conn.close()


def remover_admin(nome_ou_email):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "UPDATE passageiros SET is_admin = 0 WHERE nome = ? OR email = ?",
        (nome_ou_email, nome_ou_email),
    )
    conn.commit()
    conn.close()


def garantir_samir_admin():
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM passageiros WHERE nome = ? OR email = ?",
        ("Samir", "sam@gmail.com"),
    )
    resultado = cur.fetchone()
    if resultado is None:
        cur.execute(
            "INSERT INTO passageiros (nome, email, senha, is_admin, is_owner) VALUES (?, ?, ?, 1, 1)",
            ("Samir", "sam@gmail.com", "123"),
        )
    else:
        cur.execute(
            "UPDATE passageiros SET email = ?, senha = ?, is_admin = 1, is_owner = 1 WHERE nome = ? OR email = ?",
            ("sam@gmail.com", "123", "Samir", "sam@gmail.com"),
        )
    conn.commit()
    conn.close()


def is_owner(user):
    return bool(user and len(user) > 5 and user[5])


def obter_entradas_passa(veiculo_placa=None):
    conn_entrada = sqlite3.connect(DB_ENTRADA)
    cur_entrada = conn_entrada.cursor()
    if veiculo_placa:
        cur_entrada.execute(
            "SELECT id, nome, veiculo_placa, ida_volta FROM entrada_passa WHERE veiculo_placa = ?",
            (veiculo_placa,),
        )
    else:
        cur_entrada.execute(
            "SELECT id, nome, veiculo_placa, ida_volta FROM entrada_passa")
    rows = cur_entrada.fetchall()
    conn_entrada.close()
    return rows


def salvar_relatorio_reabertura(tipo, veiculo_placa, motorista, fechamento_hora, reabertura_hora, passageiros):
    if passageiros is None:
        passageiros = []

    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO relatorios_reabertura (tipo, veiculo_placa, motorista, data_hora, fechamento_hora, reabertura_hora, passageiros_json, total_passageiros) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            tipo,
            veiculo_placa,
            motorista,
            datetime.now().isoformat(timespec="seconds"),
            fechamento_hora,
            reabertura_hora,
            json.dumps(passageiros, ensure_ascii=False),
            len(passageiros),
        ),
    )
    conn.commit()
    conn.close()


def obter_relatorios_reabertura(veiculo_placa=None):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    if veiculo_placa:
        cur.execute(
            "SELECT id, tipo, veiculo_placa, motorista, data_hora, fechamento_hora, reabertura_hora, passageiros_json, total_passageiros FROM relatorios_reabertura WHERE veiculo_placa = ? ORDER BY data_hora DESC",
            (veiculo_placa,),
        )
    else:
        cur.execute(
            "SELECT id, tipo, veiculo_placa, motorista, data_hora, fechamento_hora, reabertura_hora, passageiros_json, total_passageiros FROM relatorios_reabertura ORDER BY data_hora DESC"
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def excluir_relatorio_reabertura(relatorio_id):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM relatorios_reabertura WHERE id = ?",
        (relatorio_id,),
    )
    conn.commit()
    conn.close()


def excluir_todos_relatorios_reabertura():
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute("DELETE FROM relatorios_reabertura")
    conn.commit()
    conn.close()


def parse_horarios_text(texto):
    horarios = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [parte.strip() for parte in linha.split("-")]
        if len(partes) < 2:
            continue

        hora = partes[0]
        ponto = partes[1]
        tempo_ponto = partes[2] if len(partes) > 2 else "5 min"
        horarios.append({"hora": hora, "ponto": ponto,
                        "tempo_ponto": tempo_ponto})
    return horarios


def carregar_veiculos():
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "SELECT placa, capacidade, motorista, horarios, ativo FROM veiculos WHERE ativo = 1 ORDER BY placa"
    )
    rows = cur.fetchall()
    conn.close()

    veiculos = []
    for placa, capacidade, motorista, horarios_json, ativo in rows:
        try:
            horarios = json.loads(horarios_json or "[]")
        except json.JSONDecodeError:
            horarios = []
        veiculos.append(
            {
                "placa": placa,
                "capacidade": capacidade,
                "motorista": motorista,
                "horarios": horarios,
                "ativo": ativo,
            }
        )
    return veiculos


def get_veiculo(placa):
    veiculos = carregar_veiculos()
    for veiculo in veiculos:
        if veiculo["placa"] == placa:
            return veiculo
    return None


def salvar_veiculo(placa, capacidade, motorista, horarios_texto):
    horarios = parse_horarios_text(horarios_texto)
    if not horarios:
        return False, "Informe ao menos um horário válido no formato: HH:MM - Ponto - tempo"

    try:
        capacidade_num = int(capacidade)
    except (TypeError, ValueError):
        return False, "Capacidade deve ser um número inteiro."

    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO veiculos (placa, capacidade, motorista, horarios, ativo) VALUES (?, ?, ?, ?, 1)",
        (
            placa.strip().upper(),
            capacidade_num,
            motorista.strip(),
            json.dumps(horarios, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return True, f"Veículo {placa.strip().upper()} salvo com sucesso!"


def excluir_veiculo(placa):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute("UPDATE veiculos SET ativo = 0 WHERE placa = ?", (placa,))
    conn.commit()
    conn.close()
    return True, f"Veículo {placa} desativado."


def carregar_lista_config():
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "SELECT status, fechamento_hora, reabertura_hora FROM lista_config WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"status": row[0], "fechamento_hora": row[1], "reabertura_hora": row[2]}
    return {"status": "aberta", "fechamento_hora": None, "reabertura_hora": None}


def carregar_lista_config_veiculo(veiculo_placa):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "SELECT status, fechamento_hora, reabertura_hora FROM lista_config_veiculo WHERE veiculo_placa = ?",
        (veiculo_placa,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return {"status": row[0], "fechamento_hora": row[1], "reabertura_hora": row[2]}
    return {"status": "aberta", "fechamento_hora": None, "reabertura_hora": None}


def atualizar_lista_config(status, fechamento_hora=None, reabertura_hora=None):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO lista_config (id, status, fechamento_hora, reabertura_hora) VALUES (1, ?, ?, ?)",
        (status, fechamento_hora, reabertura_hora),
    )
    conn.commit()
    conn.close()


def atualizar_lista_config_veiculo(veiculo_placa, status, fechamento_hora=None, reabertura_hora=None):
    conn = sqlite3.connect(DB_CADASTRO)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO lista_config_veiculo (veiculo_placa, status, fechamento_hora, reabertura_hora) VALUES (?, ?, ?, ?)",
        (veiculo_placa, status, fechamento_hora, reabertura_hora),
    )
    conn.commit()
    conn.close()


def limpar_lista_entrada():
    conn = sqlite3.connect(DB_ENTRADA)
    cur = conn.cursor()
    cur.execute("DELETE FROM entrada_passa")
    conn.commit()
    conn.close()


def limpar_lista_entrada_veiculo(veiculo_placa):
    conn = sqlite3.connect(DB_ENTRADA)
    cur = conn.cursor()
    cur.execute("DELETE FROM entrada_passa WHERE veiculo_placa = ?",
                (veiculo_placa,))
    conn.commit()
    conn.close()


def verificar_lista_config():
    config = carregar_lista_config()
    agora = datetime.now()

    # se estiver aberta e houver horário de fechamento programado
    if config.get("status") == "aberta" and config.get("fechamento_hora"):
        fechamento = datetime.combine(
            agora.date(), time.fromisoformat(config["fechamento_hora"]))
        if agora >= fechamento:
            # fecha a lista global e mantém reabertura se houver
            atualizar_lista_config("fechada", config.get(
                "fechamento_hora"), config.get("reabertura_hora"))
            config = carregar_lista_config()
            return config

    # se estiver fechada e houver horário de reabertura programado
    if config.get("status") == "fechada" and config.get("reabertura_hora"):
        reabertura = datetime.combine(
            agora.date(), time.fromisoformat(config["reabertura_hora"]))
        if agora >= reabertura:
            reabrir_lista_limpa()
            config = carregar_lista_config()
            return config

    return config


def verificar_lista_config_veiculo(veiculo_placa):
    config = carregar_lista_config_veiculo(veiculo_placa)
    agora = datetime.now()

    if config.get("status") == "aberta" and config.get("fechamento_hora"):
        fechamento = datetime.combine(
            agora.date(), time.fromisoformat(config["fechamento_hora"]))
        if agora >= fechamento:
            atualizar_lista_config_veiculo(
                veiculo_placa, "fechada", config.get("fechamento_hora"), config.get("reabertura_hora") if config.get("reabertura_hora") else None)
            config = carregar_lista_config_veiculo(veiculo_placa)
            return config

    if config.get("status") == "fechada" and config.get("reabertura_hora"):
        reabertura = datetime.combine(
            agora.date(), time.fromisoformat(config["reabertura_hora"]))
        if agora >= reabertura:
            reabrir_lista_veiculo(veiculo_placa)
            config = carregar_lista_config_veiculo(veiculo_placa)
            return config

    return config


def fechar_lista(hora):
    try:
        fechamento_hora = time.fromisoformat(hora)
    except ValueError:
        return False, "Formato inválido. Use HH:MM."

    agora = datetime.now()
    fechamento = datetime.combine(agora.date(), fechamento_hora)
    if agora >= fechamento:
        atualizar_lista_config("fechada", hora)
        return True, f"Lista fechada em {hora}."

    atualizar_lista_config("aberta", hora)
    return True, f"Lista agendada para fechar às {hora}. Novas inscrições serão bloqueadas a partir deste horário."


def fechar_lista_veiculo(veiculo_placa, hora):
    try:
        fechamento_hora = time.fromisoformat(hora)
    except ValueError:
        return False, "Formato inválido. Use HH:MM."

    agora = datetime.now()
    fechamento = datetime.combine(agora.date(), fechamento_hora)
    if agora >= fechamento:
        atualizar_lista_config_veiculo(veiculo_placa, "fechada", hora)
        return True, f"Lista do veículo {veiculo_placa} fechada em {hora}."

    atualizar_lista_config_veiculo(veiculo_placa, "aberta", hora)
    return True, f"Lista do veículo {veiculo_placa} agendada para fechar às {hora}. Novas inscrições serão bloqueadas a partir deste horário."


def reabrir_lista_veiculo(veiculo_placa):
    cfg = carregar_lista_config_veiculo(veiculo_placa)
    passageiros = obter_entradas_passa(veiculo_placa)
    passageiros_registro = [
        {
            "id": row[0],
            "nome": row[1],
            "veiculo_placa": row[2],
            "ida_volta": row[3],
        }
        for row in passageiros
    ]
    veiculo = get_veiculo(veiculo_placa)
    motorista = veiculo.get("motorista") if veiculo else None
    salvar_relatorio_reabertura(
        "veiculo",
        veiculo_placa,
        motorista,
        cfg.get("fechamento_hora"),
        cfg.get("reabertura_hora"),
        passageiros_registro,
    )
    limpar_lista_entrada_veiculo(veiculo_placa)
    atualizar_lista_config_veiculo(veiculo_placa, "aberta", None)
    return True, f"Lista do veículo {veiculo_placa} reaberta e limpa."


def reabrir_lista_limpa():
    config = carregar_lista_config()
    passageiros = obter_entradas_passa()
    passageiros_registro = [
        {
            "id": row[0],
            "nome": row[1],
            "veiculo_placa": row[2],
            "ida_volta": row[3],
        }
        for row in passageiros
    ]
    salvar_relatorio_reabertura(
        "global",
        None,
        None,
        config.get("fechamento_hora"),
        config.get("reabertura_hora"),
        passageiros_registro,
    )
    limpar_lista_entrada()
    atualizar_lista_config("aberta", None)
    return True, "Lista reaberta e limpa para as próximas viagens."


def abrir_lista_imediatamente():
    """Abre a lista imediatamente, mantendo o horário agendado de reabertura"""
    config = carregar_lista_config()
    reabertura_hora = config.get("reabertura_hora")
    atualizar_lista_config("aberta", None, reabertura_hora)
    return True, "Lista aberta."


def abrir_lista_veiculo_imediatamente(veiculo_placa):
    """Abre a lista do veículo imediatamente, mantendo o horário agendado de reabertura"""
    config = carregar_lista_config_veiculo(veiculo_placa)
    reabertura_hora = config.get("reabertura_hora")
    atualizar_lista_config_veiculo(
        veiculo_placa, "aberta", None, reabertura_hora)
    return True, f"Lista do veículo {veiculo_placa} aberta imediatamente."


def inserir_entrada_passa(nome, veiculo_placa, ida_volta):
    # checa se as listas globais e do veículo estão abertas
    global_config = verificar_lista_config()
    if global_config["status"] != "aberta":
        hora = global_config.get("fechamento_hora") or "--"
        return False, f"A lista está fechada até {hora}."

    # checar fechamento por veículo
    veh_config = verificar_lista_config_veiculo(veiculo_placa)
    if veh_config["status"] != "aberta":
        hora = veh_config.get("fechamento_hora") or "--"
        return False, f"A lista deste veículo ({veiculo_placa}) está fechada até {hora}."

    veiculo = get_veiculo(veiculo_placa)
    if not veiculo:
        return False, f"Veículo {veiculo_placa} não encontrado."

    conn_entrada = sqlite3.connect(DB_ENTRADA)
    cur_entrada = conn_entrada.cursor()

    cur_entrada.execute("SELECT 1 FROM entrada_passa WHERE nome = ?", (nome,))
    if cur_entrada.fetchone():
        conn_entrada.close()
        return False, "Você já está em uma lista."

    cur_entrada.execute(
        "SELECT COUNT(*) FROM entrada_passa WHERE veiculo_placa = ?", (veiculo_placa,))
    count = cur_entrada.fetchone()[0]
    capacidade_maxima = int(veiculo["capacidade"])

    if count >= capacidade_maxima:
        conn_entrada.close()
        return False, f"Veículo {veiculo_placa} está cheio! Capacidade: {capacidade_maxima} passageiros."

    try:
        cur_entrada.execute(
            "INSERT INTO entrada_passa (nome, veiculo_placa, ida_volta) VALUES (?, ?, ?)",
            (nome, veiculo_placa, ida_volta),
        )
        conn_entrada.commit()
        conn_entrada.close()
        return True, "Inserido na lista com sucesso!"
    except sqlite3.IntegrityError:
        conn_entrada.close()
        return False, "Você já está neste veículo."
    except Exception as e:
        conn_entrada.close()
        return False, f"Erro ao inserir: {str(e)}"


def remover_entrada_passa(nome, veiculo_placa):
    try:
        conn_entrada = sqlite3.connect(DB_ENTRADA)
        cur_entrada = conn_entrada.cursor()
        cur_entrada.execute(
            "DELETE FROM entrada_passa WHERE nome = ? AND veiculo_placa = ?",
            (nome, veiculo_placa),
        )
        conn_entrada.commit()
        conn_entrada.close()
        return True, "Removido da lista com sucesso!"
    except Exception as e:
        return False, f"Erro ao remover: {str(e)}"


ensure_database_schema()


def salvar_settings(settings):
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except Exception:
        pass


def carregar_settings():
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return {}
    return {}


def salvar_tema(modo_escuro):
    settings = carregar_settings()
    settings["tema_escuro"] = modo_escuro
    salvar_settings(settings)


def carregar_tema():
    settings = carregar_settings()
    return bool(settings.get("tema_escuro", False))


def main(page: ft.Page):

    # estado da sessão e elementos principais da UI
    user_logado = [None]
    current_view = ["home"]
    last_view = ["home"]
    welcome_text = ft.Text("Bem vindo ao Vaidbusão!", size=28,
                           weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)
    welcome_text.visible = True

    def set_welcome_text_visibility(visible):
        welcome_text.visible = visible

    def show_screen(content, *, with_nav=True, welcome_visible=None):
        if welcome_visible is not None:
            set_welcome_text_visibility(welcome_visible)
        main_container.content = ft.Column(
            [content, barra_nav], spacing=0, expand=True) if with_nav else content
        page.update()

    def switch_to_register(e):
        show_screen(register_container, with_nav=False, welcome_visible=False)

    def switch_to_login(e):
        show_screen(login_container, with_nav=False, welcome_visible=True)

    def is_user_admin():
        return bool(user_logado[0] and user_logado[0][4])

    def go_to_veiculos(e):
        current_view[0] = "veiculos"
        set_appbar("Veículos", show_back=True, show_settings=False)
        refresh_admin_panel()
        refresh_veiculos_page()
        show_screen(veiculos_page, welcome_visible=False)

    def go_to_passageiros(e):
        current_view[0] = "passageiros"
        set_appbar("Passageiros", show_back=True, show_settings=False)
        show_screen(passageiros_page, welcome_visible=False)

    def go_to_admin_panel(e):
        current_view[0] = "admin"
        set_appbar("Painel ADM", show_back=True, show_settings=False)
        refresh_admin_panel()
        show_screen(admin_page, welcome_visible=False)

    def go_to_home(e):
        current_view[0] = "home"
        barra_nav.selected_index = 0
        refresh_home_access()
        set_appbar("VaidBusão", show_back=False,
                   show_settings=True, show_notifications=True)
        show_screen(Home_container, welcome_visible=True)

    def go_to_mapa(e):
        current_view[0] = "mapa"
        barra_nav.selected_index = 1
        set_appbar("Mapa", show_back=False,
                   show_settings=True, show_notifications=True)
        show_screen(mapa_container, welcome_visible=False)

    def restore_previous_view():
        previous = last_view[0] or "home"
        if previous == "home":
            go_to_home(None)
        elif previous == "mapa":
            go_to_mapa(None)
        elif previous == "veiculos":
            go_to_veiculos(None)
        elif previous == "passageiros":
            go_to_passageiros(None)
        elif previous == "admin":
            go_to_admin_panel(None)
        else:
            go_to_home(None)

    def go_back_from_settings(e):
        restore_previous_view()

    def mudanca_nav(e):
        index = e.control.selected_index
        if index == 0:
            go_to_home(e)
        elif index == 1:
            go_to_mapa(e)

    theme_dark = [carregar_tema()]
    unread_notifications = [False]
    manual_notifications = []

    def tc():
        return ft.Colors.WHITE if theme_dark[0] else ft.Colors.BLACK

    def header_color():
        return ft.Colors.BLUE_900 if theme_dark[0] else ft.Colors.BLUE

    def render_appbar_for_current_view():
        if current_view[0] == "home":
            set_appbar("VaidBusão", show_back=False,
                       show_settings=True, show_notifications=True)
        elif current_view[0] == "mapa":
            set_appbar("Mapa", show_back=False,
                       show_settings=True, show_notifications=True)
        elif current_view[0] == "veiculos":
            set_appbar("Veículos", show_back=True, show_settings=False)
        elif current_view[0] == "passageiros":
            set_appbar("Passageiros", show_back=True, show_settings=False)
        elif current_view[0] == "settings":
            set_appbar("Configurações", show_back=True,
                       show_settings=False, show_notifications=False, back_action=go_back_from_settings)
        elif current_view[0] == "notifications":
            set_appbar("Notificações", show_back=True,
                       show_settings=True, show_notifications=False, back_action=go_back_from_settings)
        elif current_view[0] == "relatorios":
            set_appbar("Relatórios", show_back=True,
                       show_settings=True, show_notifications=True, back_action=go_back_from_settings)
        elif current_view[0] == "admin":
            set_appbar("Painel ADM", show_back=True,
                       show_settings=False, show_notifications=False, back_action=go_back_from_settings)

    def set_appbar(title, show_back=False, show_settings=True, show_notifications=False, back_action=None):
        actions = []
        if show_notifications:
            notification_badge = ft.Container(
                width=10,
                height=10,
                bgcolor=ft.Colors.RED,
                border_radius=10,
                visible=unread_notifications[0],
                margin=ft.Margin.only(left=2),
            )
            actions.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.NOTIFICATIONS,
                                    color=ft.Colors.WHITE),
                            notification_badge,
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=go_to_notifications,
                    padding=ft.Padding.only(right=8),
                )
            )
        if show_settings:
            actions.append(ft.IconButton(
                ft.Icons.SETTINGS, on_click=go_to_settings))
        page.appbar = ft.AppBar(
            title=ft.Text(title),
            bgcolor=header_color(),
            color=ft.Colors.WHITE,
            leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                  on_click=back_action or go_to_home) if show_back else None,
            actions=actions,
        )

    def create_tile(icon, label, on_click):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=30, color=ft.Colors.BLACK),
                ft.Text(label, size=12, color=ft.Colors.BLACK,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER, spacing=5),
            bgcolor=ft.Colors.CYAN_200,
            padding=15,
            border_radius=10,
            ink=True,
            on_click=on_click,
            width=100,
            height=100,
        )

    def refresh_home_access():
        admin_tile.visible = is_user_admin()
        atualizar_home_relatorio_widget()
        if current_view[0] == "home":
            page.update()

    def handle_toggle_theme(e):
        theme_dark[0] = e.control.value
        salvar_tema(theme_dark[0])
        page.bgcolor = ft.Colors.BLACK if theme_dark[0] else ft.Colors.WHITE
        barra_nav.bgcolor = header_color()
        if page.appbar:
            page.appbar.bgcolor = header_color()
            page.appbar.color = ft.Colors.WHITE
        apply_theme()
        go_to_settings(e)

    def apply_theme():
        if page.appbar:
            page.appbar.bgcolor = header_color()
            page.appbar.color = ft.Colors.WHITE

        barra_nav.bgcolor = header_color()
        page.controls[0].controls[0].color = header_color()
        login_container.content.controls[0].color = header_color()
        register_container.content.controls[0].color = header_color()
        Home_container.content.controls[0].color = tc()

        mapa_subtitle_text.color = tc()
        mapa_info_text.color = tc()
        legenda_principal_text.color = tc()
        legenda_universidade_text.color = tc()
        legenda_onibus_text.color = tc()
        mapa_container.border = ft.Border.all(1, map_border_color())
        mapa_container.bgcolor = map_bgcolor()
        mapa_row = mapa_container.content.controls[2]
        mapa_row.controls[1].bgcolor = map_bgcolor()
        mapa_row.controls[1].border = ft.Border.all(1, map_border_color())
        mapa_viewer_content.bgcolor = map_bgcolor()
        mapa_error_content.bgcolor = map_bgcolor()
        legenda_container.bgcolor = map_bgcolor()
        legenda_container.border = ft.Border.all(1, map_border_color())

        for fld in [login_username, login_password, register_name, register_email, register_password, register_confirm]:
            fld.text_style = ft.TextStyle(color=tc())

        passageiros_table.heading_text_style = ft.TextStyle(color=tc())
        passageiros_table.data_text_style = ft.TextStyle(color=tc())
        passageiros_message.color = tc()
        passageiros_feedback.color = tc()

        relatorios_table.heading_text_style = ft.TextStyle(color=tc())
        relatorios_table.data_text_style = ft.TextStyle(color=tc())
        relatorios_summary.color = tc()
        relatorios_feedback.color = ft.Colors.RED

        veiculo_dropdown.text_style = ft.TextStyle(color=tc())
        veiculo_dropdown.label_style = ft.TextStyle(color=tc())
        veiculo_dropdown.border_color = ft.Colors.BLUE
        ida_volta_dropdown.text_style = ft.TextStyle(color=tc())
        ida_volta_dropdown.label_style = ft.TextStyle(color=tc())
        ida_volta_dropdown.border_color = ft.Colors.BLUE

        relatorios_selection.border_color = ft.Colors.BLUE
        relatorios_selection.filled = True
        relatorios_selection.fill_color = ft.Colors.BLACK if theme_dark[0] else ft.Colors.WHITE
        relatorios_selection.hover_color = ft.Colors.BLUE_900 if theme_dark[
            0] else ft.Colors.BLUE_50
        relatorios_selection.text_style = ft.TextStyle(color=tc())
        relatorios_selection.label_style = ft.TextStyle(color=tc())
        relatorios_selection.hint_style = ft.TextStyle(color=tc())
        relatorios_selection.menu_style = ft.TextStyle(color=tc())

        admin_vehicle_placa.text_style = ft.TextStyle(color=tc())
        admin_vehicle_capacidade.text_style = ft.TextStyle(color=tc())
        admin_vehicle_motorista.text_style = ft.TextStyle(color=tc())
        admin_vehicle_horarios.text_style = ft.TextStyle(color=tc())
        admin_promote_field.text_style = ft.TextStyle(color=tc())
        admin_lista_hora.text_style = ft.TextStyle(color=tc())
        admin_lista_feedback.color = tc()

    def build_notifications():
        now = datetime.now()
        items = []
        for placa, entradas in get_vehicle_schedule_data().items():
            for item in entradas:
                schedule_dt = datetime.combine(
                    now.date(), datetime.strptime(item["hora"], "%H:%M").time())
                diff = (schedule_dt - now).total_seconds() / 60
                if -5 <= diff <= 10:
                    if diff >= 0:
                        status = "vai para"
                        texto = f"{placa} vai para o ponto {item['ponto']} em {int(diff)} min."
                        cor = ft.Colors.ORANGE_800
                        bg = ft.Colors.ORANGE_100 if not theme_dark[0] else ft.Colors.ORANGE_900
                    else:
                        status = "chegou"
                        texto = f"{placa} chegou ao ponto {item['ponto']} agora."
                        cor = ft.Colors.GREEN_800
                        bg = ft.Colors.GREEN_100 if not theme_dark[0] else ft.Colors.GREEN_900
                    items.append((status, texto, cor, bg))

        items.extend(manual_notifications)

        if not items:
            items.append((
                "nenhuma",
                "Nenhuma notificação no momento. Verifique novamente mais perto dos horários programados.",
                ft.Colors.GREY_800,
                ft.Colors.GREY_100 if not theme_dark[0] else ft.Colors.GREY_900,
            ))
        return items

    def refresh_notifications():
        cards = []
        for status, texto, cor, bg in build_notifications():
            if status == "nenhuma":
                cards.append(
                    ft.Container(
                        content=ft.Text(texto, size=15, color=tc()),
                        bgcolor=bg,
                        padding=15,
                        border_radius=10,
                    )
                )
            else:
                cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(status.title(), size=16,
                                    weight=ft.FontWeight.BOLD, color=cor),
                            ft.Text(texto, size=14, color=tc()),
                        ], spacing=6),
                        bgcolor=bg,
                        padding=15,
                        border_radius=10,
                    )
                )
        notifications_list_container.controls = cards
        if current_view[0] == "notifications":
            page.update()

    def simulate_notification(e):
        manual_notifications.append((
            "simulado",
            "Ônibus ABC-1234 está indo para o ponto Centro.",
            ft.Colors.BLUE_800,
            ft.Colors.BLUE_100 if not theme_dark[0] else ft.Colors.BLUE_900,
        ))
        unread_notifications[0] = True
        render_appbar_for_current_view()
        refresh_notifications()
        page.update()

    def toggle_password(field, button, e):
        field.password = not field.password
        button.icon = ft.Icons.VISIBILITY if field.password else ft.Icons.VISIBILITY_OFF
        page.update()

    def go_to_settings(e):
        last_view[0] = current_view[0]
        current_view[0] = "settings"
        set_welcome_text_visibility(False)
        set_appbar("Configurações", show_back=True,
                   show_settings=False, show_notifications=False, back_action=go_back_from_settings)
        header_color = ft.Colors.BLUE_900 if theme_dark[0] else ft.Colors.BLUE
        settings_page = ft.Container(
            content=ft.Column([
                ft.Container(content=ft.Text("Configurações", size=24,
                             color=header_color, weight=ft.FontWeight.BOLD), padding=20),
                ft.Row([
                    ft.Text("Modo Escuro", size=16, color=tc()),
                    ft.Switch(value=theme_dark[0],
                              on_change=handle_toggle_theme,
                              animate_opacity=ft.Animation(300, "easeInOut")),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=20),
            expand=True,
            padding=20,
        )
        main_container.content = ft.Column(
            [settings_page, barra_nav], spacing=0, expand=True)
        page.update()

    def go_to_notifications(e):
        last_view[0] = current_view[0]
        current_view[0] = "notifications"
        unread_notifications[0] = False
        set_welcome_text_visibility(False)
        set_appbar("Notificações", show_back=True,
                   show_settings=True, show_notifications=False, back_action=go_back_from_settings)
        refresh_notifications()
        main_container.content = ft.Column(
            [notifications_page, barra_nav], spacing=0, expand=True)
        page.update()

    async def handle_login(e):
        email = login_username.value
        senha = login_password.value

        if not email or not senha:
            login_message.value = "Preencha todos os campos!"
            login_message.color = ft.Colors.RED
            page.update()
            return

        login_button.disabled = True
        login_progress.visible = True
        page.update()
        await asyncio.sleep(1)

        try:
            sucesso, mensagem, usuario = fazer_login(email, senha)
            login_message.value = mensagem
            login_message.color = ft.Colors.GREEN if sucesso else ft.Colors.RED

            if sucesso:
                user_logado[0] = usuario
                refresh_home_access()
                refresh_vehicle_dropdown()
                atualizar_tabela_passageiros()
                refresh_veiculos_page()

                set_appbar("VaidBusão", show_back=False,
                           show_settings=True, show_notifications=True)

                login_username.value = ""
                login_password.value = ""
                main_container.content = ft.Column(
                    [Home_container, barra_nav], spacing=0, expand=True)
                page.controls[0].controls.pop(0)
        finally:
            login_button.disabled = False
            login_progress.visible = False
            page.update()

    def handle_register(e):
        nome = register_name.value
        email = register_email.value
        senha = register_password.value
        confirmar = register_confirm.value

        if not nome or not email or not senha or not confirmar:
            register_message.value = "Preencha todos os campos!"
            register_message.color = ft.Colors.RED
            page.update()
            return

        if senha != confirmar:
            register_message.value = "As senhas não conferem!"
            register_message.color = ft.Colors.RED
            page.update()

            return

        sucesso, mensagem = cadastro_passageiro(nome, email, senha)

        if sucesso:
            login_message.value = mensagem
            login_message.color = ft.Colors.GREEN
            register_name.value = ""
            register_email.value = ""
            register_password.value = ""
            register_confirm.value = ""
            main_container.content = login_container
            page.update()
        else:
            register_message.value = mensagem
            register_message.color = ft.Colors.RED
            page.update()

    page.bgcolor = ft.Colors.BLACK if theme_dark[0] else ft.Colors.WHITE
    page.window_width = 390
    page.window_height = 844
    page.window_resizable = False

    login_username = ft.TextField(
        label="Usuário", width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()))

    toggle_btn_login = ft.IconButton(
        icon=ft.Icons.VISIBILITY, icon_color=ft.Colors.BLUE, icon_size=20)
    toggle_btn_login.on_click = lambda e: toggle_password(
        login_password, toggle_btn_login, e)
    login_password = ft.TextField(
        label="Senha", password=True, width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()),
        suffix=toggle_btn_login)

    login_button = ft.Button(
        "Entrar", bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, width=300, on_click=handle_login)

    login_progress = ft.ProgressRing(visible=False)

    login_message = ft.Text("", color=ft.Colors.RED, size=12)

    login_container = ft.Container(
        content=ft.Column([
            ft.Text("Login", size=30, color=ft.Colors.BLUE,
                    weight=ft.FontWeight.BOLD),
            login_username,
            login_password,
            login_button,
            login_progress,
            login_message,
            ft.Row([
                ft.Text("Não é cadastrado? Cadastre-se agora!",
                        color=tc()),
                ft.Button("Cadastrar", on_click=switch_to_register)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
        alignment=ft.Alignment.CENTER,
        padding=20
    )

    register_name = ft.TextField(
        label="Nome", width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()))
    register_email = ft.TextField(
        label="Email", width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()))

    toggle_btn_register = ft.IconButton(
        icon=ft.Icons.VISIBILITY, icon_color=ft.Colors.BLUE, icon_size=20)
    toggle_btn_register.on_click = lambda e: toggle_password(
        register_password, toggle_btn_register, e)

    register_password = ft.TextField(
        label="Senha", password=True, width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()),
        suffix=toggle_btn_register)

    toggle_btn_confirm = ft.IconButton(
        icon=ft.Icons.VISIBILITY, icon_color=ft.Colors.BLUE, icon_size=20)
    toggle_btn_confirm.on_click = lambda e: toggle_password(
        register_confirm, toggle_btn_confirm, e)

    register_confirm = ft.TextField(
        label="Confirmar Senha", password=True, width=300, border_color=ft.Colors.BLUE, text_style=ft.TextStyle(color=tc()),
        suffix=toggle_btn_confirm)

    register_button = ft.Button(
        "Cadastrar", bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, width=300, on_click=handle_register)

    register_message = ft.Text("", color=ft.Colors.RED, size=12)

    register_container = ft.Container(
        content=ft.Column([
            ft.Text("Cadastro", size=30, color=ft.Colors.BLUE,
                    weight=ft.FontWeight.BOLD),
            register_name,
            register_email,
            register_password,
            register_confirm,
            register_button,
            register_message,
            ft.Button("Voltar ao Login",
                      on_click=switch_to_login, width=300)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
        alignment=ft.Alignment.CENTER,
        padding=20
    )

    admin_tile = create_tile(ft.Icons.ADMIN_PANEL_SETTINGS,
                             "Painel ADM", go_to_admin_panel)
    admin_tile.visible = False

    def go_to_relatorios(e):
        current_view[0] = "relatorios"
        set_appbar("Relatórios", show_back=True,
                   show_settings=True, show_notifications=True,
                   back_action=go_to_home)
        refresh_relatorios_page()
        show_screen(relatorios_page, welcome_visible=False)

    admin_relatorio_tile = create_tile(ft.Icons.INSIGHTS,
                                       "Relatórios", go_to_relatorios)
    admin_relatorio_tile.visible = False

    Home_container = ft.Container(
        content=ft.Column([
            ft.Text("HOME", size=30, color=tc(), weight=ft.FontWeight.BOLD),
            ft.Divider(color=ft.Colors.GREY_400),
            ft.Row([
                create_tile(ft.Icons.DIRECTIONS_BUS,
                            "Verificar Veículos", go_to_veiculos),
                create_tile(ft.Icons.PEOPLE,
                            "Tabela de Passageiros", go_to_passageiros),
                admin_tile,
                admin_relatorio_tile,
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
        ], alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        ),
        padding=20,
        expand=True,
    )

    def atualizar_home_relatorio_widget():
        admin_tile.visible = is_user_admin()
        admin_relatorio_tile.visible = is_user_admin()
        page.update()

    def go_to_relatorios(e):
        current_view[0] = "relatorios"
        set_appbar("Relatórios", show_back=True,
                   show_settings=True, show_notifications=True,
                   back_action=go_to_home)
        refresh_relatorios_page()
        show_screen(relatorios_page, welcome_visible=False)

    def classificar_periodo(hora):
        hora_int = int(hora.split(":")[0])
        if 5 <= hora_int < 12:
            return "manhã"
        if 12 <= hora_int < 18:
            return "tarde"
        return "noite"

    def meta_periodo(periodo):
        if periodo == "manhã":
            return ft.Icons.WB_SUNNY
        if periodo == "tarde":
            return ft.Icons.WB_SUNNY_OUTLINED
        return ft.Icons.NIGHTLIGHT_ROUNDED

    def formatar_horarios(horarios):
        linhas = []
        for item in horarios:
            periodo = classificar_periodo(item["hora"])
            icon = meta_periodo(periodo)
            linhas.append(
                ft.Row([
                    ft.Icon(icon, color=tc(), size=18),
                    ft.Text(
                        f"{item['hora']} — {item.get('ponto', 'Ponto')} — {item.get('tempo_ponto', '5 min')}",
                        size=15,
                        color=tc(),
                    ),
                ], spacing=8)
            )
        return linhas

    def create_vehicle_card(placa, capacidade, motorista, horarios):
        return ft.Container(
            content=ft.Column([
                ft.Text(f"Placa: {placa}", size=18,
                        weight=ft.FontWeight.BOLD, color=tc()),
                ft.Text(f"Capacidade: {capacidade} passageiros",
                        size=16, color=tc()),
                ft.Text(f"Motorista: {motorista}",
                        size=16, color=tc()),
                ft.Text(
                    "Horários e tempo no ponto:",
                    size=16,
                    color=tc(),
                    weight=ft.FontWeight.BOLD,
                ),
                *formatar_horarios(horarios),
            ], spacing=5),
            bgcolor=ft.Colors.BLUE_600,
            padding=20,
            border_radius=10,
            expand=True,
        )

    vehicle_cards_container = ft.Column(spacing=12)

    def get_vehicle_schedule_data():
        schedule = {}
        for veiculo in carregar_veiculos():
            schedule[veiculo["placa"]] = [
                {"hora": item["hora"], "ponto": item.get("ponto", "Ponto")}
                for item in veiculo["horarios"]
            ]
        return schedule

    def refresh_veiculos_page():
        veiculos = carregar_veiculos()
        if not veiculos:
            vehicle_cards_container.controls = [
                ft.Text("Nenhum veículo cadastrado ainda. Use o painel ADM para incluir um ônibus.",
                        color=tc(), size=15)
            ]
        else:
            vehicle_cards_container.controls = [
                create_vehicle_card(
                    veiculo["placa"],
                    veiculo["capacidade"],
                    veiculo["motorista"],
                    veiculo["horarios"],
                )
                for veiculo in veiculos
            ]
        if current_view[0] == "veiculos":
            page.update()

    admin_vehicle_placa = ft.TextField(label="Placa", width=340,
                                       border_color=ft.Colors.BLUE,
                                       text_style=ft.TextStyle(color=tc()))
    admin_vehicle_capacidade = ft.TextField(label="Capacidade", width=340,
                                            border_color=ft.Colors.BLUE,
                                            text_style=ft.TextStyle(color=tc()))
    admin_vehicle_motorista = ft.TextField(label="Motorista", width=340,
                                           border_color=ft.Colors.BLUE,
                                           text_style=ft.TextStyle(color=tc()))
    admin_vehicle_horarios = ft.TextField(
        label="Horários",
        hint_text="Ex.: 08:00 - Centro - 5 min\n14:00 - Universidade - 7 min",
        multiline=True,
        min_lines=4,
        width=340,
        border_color=ft.Colors.BLUE,
        text_style=ft.TextStyle(color=tc()),
    )
    admin_vehicle_button = ft.Button("Salvar veículo", bgcolor=ft.Colors.GREEN,
                                     color=ft.Colors.WHITE)
    admin_vehicle_feedback = ft.Text("", size=12, color=ft.Colors.GREEN)
    admin_vehicle_remove_placa = ft.TextField(label="Placa para remover", width=340,
                                              border_color=ft.Colors.RED,
                                              text_style=ft.TextStyle(color=tc()))
    admin_vehicle_remove_button = ft.Button("Remover veículo", bgcolor=ft.Colors.RED,
                                            color=ft.Colors.WHITE)
    admin_vehicle_remove_feedback = ft.Text("", size=12, color=ft.Colors.GREEN)
    admin_promote_field = ft.TextField(label="Nome ou e-mail", width=340,
                                       border_color=ft.Colors.BLUE,
                                       text_style=ft.TextStyle(color=tc()))
    admin_action_dropdown = ft.Dropdown(
        label="Ação ADM",
        width=340,
        options=[
            ft.dropdown.Option("promover", "Promover ADM"),
            ft.dropdown.Option("remover", "Remover ADM"),
        ],
        value="promover",
        border_color=ft.Colors.BLUE,
        text_style=ft.TextStyle(color=tc()),
        label_style=ft.TextStyle(color=tc()),
    )
    admin_promote_button = ft.Button("Aplicar ação", bgcolor=ft.Colors.BLUE,
                                     color=ft.Colors.WHITE)
    admin_promote_feedback = ft.Text("", size=12, color=ft.Colors.GREEN)
    admin_owner_controls = ft.Container(
        content=ft.Column([
            ft.Text("Gerenciar administradores", size=18,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
            admin_promote_field,
            admin_action_dropdown,
            admin_promote_button,
            admin_promote_feedback,
        ], spacing=12),
        visible=False,
    )
    admin_lista_veiculo = ft.Dropdown(
        label="Aplicar a",
        width=340,
        options=[],
        value="__global__",
        border_color=ft.Colors.BLUE,
        text_style=ft.TextStyle(color=tc()),
        label_style=ft.TextStyle(color=tc()),
    )

    admin_lista_hora = ft.TextField(label="Fechar lista até", hint_text="HH:MM",
                                    width=340, border_color=ft.Colors.BLUE,
                                    text_style=ft.TextStyle(color=tc()))
    admin_reopen_hora = ft.TextField(label="Reabrir em", hint_text="HH:MM",
                                     width=340, border_color=ft.Colors.BLUE,
                                     text_style=ft.TextStyle(color=tc()))
    admin_close_button = ft.Button("Fechar lista", bgcolor=ft.Colors.ORANGE,
                                   color=ft.Colors.WHITE)
    admin_reopen_button = ft.Button("Agendar reabertura", bgcolor=ft.Colors.RED,
                                    color=ft.Colors.WHITE)
    admin_open_immediately_button = ft.Button("Reabrir lista", bgcolor=ft.Colors.GREEN,
                                              color=ft.Colors.WHITE)
    admin_lista_feedback = ft.Text("", size=12, color=ft.Colors.BLUE)

    admin_panel_container = ft.Container(
        content=ft.Column([
            ft.Text("Painel de administrador", size=22,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
            ft.Text(
                "Cadastre novos veículos, promova outro usuário para ADM e finalize a lista de passageiros.",
                size=14,
                color=tc(),
            ),
            ft.Divider(color=ft.Colors.GREY_400),
            ft.Text("Adicionar ou editar veículo", size=18,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
            admin_vehicle_placa,
            admin_vehicle_capacidade,
            admin_vehicle_motorista,
            admin_vehicle_horarios,
            admin_vehicle_button,
            admin_vehicle_feedback,
            ft.Text("Remover veículo", size=18,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
            admin_vehicle_remove_placa,
            admin_vehicle_remove_button,
            admin_vehicle_remove_feedback,
            admin_owner_controls,
            ft.Text("Finalização da lista", size=18,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
            admin_lista_veiculo,
            admin_lista_hora,
            admin_reopen_hora,
            ft.Row([
                admin_close_button,
                admin_reopen_button,
                admin_open_immediately_button,
            ], spacing=10),
            admin_lista_feedback,
        ], spacing=12, scroll=ft.ScrollMode.ADAPTIVE),
        padding=20,
        visible=False,
        expand=True,
    )

    def refresh_admin_panel():
        # atualizar opções do dropdown de alvo (global ou veículos)
        veiculos = carregar_veiculos()
        options = [ft.dropdown.Option("__global__", "Todas (Global)")]
        for v in veiculos:
            options.append(ft.dropdown.Option(v["placa"], v["placa"]))
        admin_lista_veiculo.options = options
        if admin_lista_veiculo.value not in [opt.key for opt in options]:
            admin_lista_veiculo.value = "__global__"

        # mostrar status conforme seleção
        target = admin_lista_veiculo.value or "__global__"
        if target == "__global__":
            config = verificar_lista_config()
            if config["status"] == "aberta":
                if config["fechamento_hora"]:
                    agora = datetime.now()
                    fechamento = datetime.combine(
                        agora.date(), time.fromisoformat(config["fechamento_hora"]))
                    if agora < fechamento:
                        admin_lista_feedback.value = f"Lista aberta. Agendada para fechar às {config['fechamento_hora']}."
                    else:
                        admin_lista_feedback.value = f"Lista aberta. Fechamento programado para hoje às {config['fechamento_hora']} está sendo processado."
                else:
                    admin_lista_feedback.value = "Lista aberta. Configure um horário para fechar e salvar o relatório do dia."
                admin_lista_feedback.color = ft.Colors.BLUE
            else:
                admin_lista_feedback.value = f"Lista fechada. Relatório salvo para hoje." if config[
                    "fechamento_hora"] else "Lista fechada."
                admin_lista_feedback.color = ft.Colors.ORANGE
            # preencher campos com valores salvos
            admin_lista_hora.value = config.get("fechamento_hora") or ""
            admin_reopen_hora.value = config.get("reabertura_hora") or ""
        else:
            placa = target
            cfg = carregar_lista_config_veiculo(placa)
            if cfg["status"] == "aberta":
                if cfg["fechamento_hora"]:
                    agora = datetime.now()
                    fechamento = datetime.combine(
                        agora.date(), time.fromisoformat(cfg["fechamento_hora"]))
                    if agora < fechamento:
                        admin_lista_feedback.value = f"Lista do {placa} aberta. Agendada para fechar às {cfg['fechamento_hora']}."
                    else:
                        admin_lista_feedback.value = f"Lista do {placa} aberta. Fechamento programado para hoje às {cfg['fechamento_hora']} está sendo processado."
                else:
                    admin_lista_feedback.value = f"Lista do {placa} aberta. Configure um horário para fechar e salvar o relatório do dia."
                admin_lista_feedback.color = ft.Colors.BLUE
            else:
                admin_lista_feedback.value = f"Lista do {placa} fechada. Relatório salvo para hoje." if cfg[
                    "fechamento_hora"] else f"Lista do {placa} fechada."
                admin_lista_feedback.color = ft.Colors.ORANGE
            # preencher campos com valores salvos para o veículo
            admin_lista_hora.value = cfg.get("fechamento_hora") or ""
            admin_reopen_hora.value = cfg.get("reabertura_hora") or ""

        is_owner_user = is_owner(user_logado[0])
        admin_owner_controls.visible = is_owner_user
        admin_panel_container.visible = is_user_admin()
        page.update()

    def handle_save_vehicle(e):
        sucesso, mensagem = salvar_veiculo(
            admin_vehicle_placa.value,
            admin_vehicle_capacidade.value,
            admin_vehicle_motorista.value,
            admin_vehicle_horarios.value,
        )
        admin_vehicle_feedback.value = mensagem
        admin_vehicle_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        refresh_veiculos_page()
        refresh_vehicle_dropdown()
        atualizar_tabela_passageiros()
        page.update()

    def handle_remove_vehicle(e):
        placa = admin_vehicle_remove_placa.value.strip().upper()
        if not placa:
            admin_vehicle_remove_feedback.value = "Informe a placa do veículo para remover."
            admin_vehicle_remove_feedback.color = ft.Colors.RED
            page.update()
            return

        sucesso, mensagem = excluir_veiculo(placa)
        admin_vehicle_remove_feedback.value = mensagem
        admin_vehicle_remove_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        admin_vehicle_remove_placa.value = ""
        refresh_veiculos_page()
        refresh_vehicle_dropdown()
        atualizar_tabela_passageiros()
        page.update()

    def handle_promote_admin(e):
        if not is_owner(user_logado[0]):
            admin_promote_feedback.value = "Apenas o dono pode gerenciar administradores."
            admin_promote_feedback.color = ft.Colors.RED
            page.update()
            return

        valor = admin_promote_field.value.strip()
        if not valor:
            admin_promote_feedback.value = "Informe um nome ou e-mail para aplicar a ação."
            admin_promote_feedback.color = ft.Colors.RED
            page.update()
            return

        if admin_action_dropdown.value == "promover":
            definir_admin(valor, True)
            admin_promote_feedback.value = f"{valor} agora é ADM."
            admin_promote_feedback.color = ft.Colors.GREEN
        else:
            remover_admin(valor)
            admin_promote_feedback.value = f"{valor} não é mais ADM."
            admin_promote_feedback.color = ft.Colors.GREEN

        page.update()

    def handle_close_list(e):
        hora = admin_lista_hora.value.strip()
        if not hora:
            admin_lista_feedback.value = "Informe o horário de fechamento no formato HH:MM."
            admin_lista_feedback.color = ft.Colors.RED
            page.update()
            return
        try:
            datetime.strptime(hora, "%H:%M")
        except ValueError:
            admin_lista_feedback.value = "Formato inválido. Use HH:MM."
            admin_lista_feedback.color = ft.Colors.RED
            page.update()
            return

        target = admin_lista_veiculo.value or "__global__"
        if target == "__global__":
            sucesso, mensagem = fechar_lista(hora)
        else:
            sucesso, mensagem = fechar_lista_veiculo(target, hora)

        admin_lista_feedback.value = mensagem
        admin_lista_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        refresh_admin_panel()
        page.update()

    def handle_reopen_list(e):
        hora = admin_reopen_hora.value.strip()
        target = admin_lista_veiculo.value or "__global__"

        if not hora:
            admin_lista_feedback.value = "Por favor, informe a hora para agendar a reabertura (HH:MM)."
            admin_lista_feedback.color = ft.Colors.RED
            page.update()
            return

        try:
            datetime.strptime(hora, "%H:%M")
        except ValueError:
            admin_lista_feedback.value = "Formato inválido. Use HH:MM."
            admin_lista_feedback.color = ft.Colors.RED
            page.update()
            return

        # agendar reabertura: lista permanece fechada
        if target == "__global__":
            atualizar_lista_config("fechada", None, hora)
            mensagem = f"Reabertura agendada para as {hora}."
        else:
            atualizar_lista_config_veiculo(target, "fechada", None, hora)
            mensagem = f"Reabertura agendada para as {hora}."

        admin_lista_feedback.value = mensagem
        admin_lista_feedback.color = ft.Colors.GREEN
        admin_reopen_hora.value = ""
        page.update()

    def handle_open_immediately(e):
        target = admin_lista_veiculo.value or "__global__"
        if target == "__global__":
            sucesso, mensagem = abrir_lista_imediatamente()
        else:
            sucesso, mensagem = abrir_lista_veiculo_imediatamente(target)

        admin_lista_feedback.value = mensagem
        admin_lista_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        refresh_admin_panel()
        atualizar_tabela_passageiros()
        page.update()

    admin_vehicle_button.on_click = handle_save_vehicle
    admin_vehicle_remove_button.on_click = handle_remove_vehicle
    admin_promote_button.on_click = handle_promote_admin
    admin_close_button.on_click = handle_close_list
    admin_reopen_button.on_click = handle_reopen_list
    admin_open_immediately_button.on_click = handle_open_immediately
    admin_lista_veiculo.on_change = lambda e: refresh_admin_panel()

    veiculos_page = ft.Container(
        content=ft.Column([
            ft.Container(content=ft.Text("Verificar Veículos", size=24,
                                         color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD), padding=20),
            ft.Container(content=ft.Text(
                "Confira abaixo os veículos disponíveis, suas placas, capacidade e motorista.", size=16, color=tc()), padding=ft.Padding.only(bottom=10)),
            vehicle_cards_container,
        ], spacing=15, scroll=ft.ScrollMode.ADAPTIVE, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True),
        expand=True,
        padding=20,
    )
    admin_page = admin_panel_container

    relatorios_selection = ft.Dropdown(
        label="Relatório",
        width=520,
        options=[],
        border_color=ft.Colors.BLUE,
        filled=True,
        fill_color=ft.Colors.BLACK if theme_dark[0] else ft.Colors.WHITE,
        hover_color=ft.Colors.BLUE_50 if not theme_dark[0] else ft.Colors.BLUE_900,
        text_style=ft.TextStyle(color=tc()),
        label_style=ft.TextStyle(color=tc()),
        hint_style=ft.TextStyle(color=tc()),
        menu_style=ft.TextStyle(color=tc()),
    )
    relatorios_feedback = ft.Text("", size=14, color=ft.Colors.RED)
    relatorios_summary = ft.Text("", size=14, color=tc())

    def formatar_data_hora(data_hora):
        try:
            dt = datetime.fromisoformat(data_hora)
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return data_hora or "N/A"

    relatorios_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("#")),
            ft.DataColumn(ft.Text("Nome")),
            ft.DataColumn(ft.Text("Veículo")),
            ft.DataColumn(ft.Text("Ida/Volta")),
        ],
        rows=[],
        width=760,
        column_spacing=20,
        heading_text_style=ft.TextStyle(color=tc()),
        data_text_style=ft.TextStyle(color=tc()),
    )

    def carregar_relatorio_selecionado(e=None):
        relatorios_feedback.value = ""
        if not relatorios_selection.value:
            relatorios_table.rows = []
            relatorios_summary.value = "Selecione um relatório para ver os passageiros."
            page.update()
            return

        relatorios = obter_relatorios_reabertura()
        registro = next(
            (r for r in relatorios if str(r[0]) == str(
                relatorios_selection.value)), None
        )
        if not registro:
            relatorios_table.rows = []
            relatorios_summary.value = "Relatório não encontrado."
            page.update()
            return

        _, tipo, placa, motorista, data_hora, fechamento_hora, reabertura_hora, passageiros_json, total = registro
        data_formatada = formatar_data_hora(data_hora)
        if tipo == "global":
            tipo_label = "Relatório Global"
            detalhe = f"Data: {data_formatada}"
        else:
            tipo_label = f"Relatório do veículo {placa}"
            detalhe = f"Placa: {placa} | Motorista: {motorista or 'N/A'} | Data: {data_formatada}"
        fechamento_text = fechamento_hora or "N/A"
        reabertura_text = reabertura_hora or "N/A"
        relatorios_summary.value = (
            f"{tipo_label} — {detalhe} | Fechamento: {fechamento_text} | "
            f"Reabertura: {reabertura_text} | Total de passageiros: {total}."
        )

        passageiros = []
        try:
            passageiros = json.loads(passageiros_json or "[]")
        except Exception:
            passageiros = []

        relatorios_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(index))),
                ft.DataCell(ft.Text(item.get("nome", ""))),
                ft.DataCell(ft.Text(item.get("veiculo_placa", ""))),
                ft.DataCell(ft.Text(item.get("ida_volta", ""))),
            ])
            for index, item in enumerate(passageiros, start=1)
        ]
        page.update()

    def excluir_relatorio_selecionado(e=None):
        if not relatorios_selection.value:
            relatorios_feedback.value = "Selecione um relatório antes de apagar."
            page.update()
            return

        excluir_relatorio_reabertura(int(relatorios_selection.value))
        relatorios_feedback.value = "Relatório excluído com sucesso."
        refresh_relatorios_page()

    def excluir_todos_relatorios(e=None):
        excluir_todos_relatorios_reabertura()
        relatorios_feedback.value = "Todos os relatórios foram removidos."
        refresh_relatorios_page()

    def refresh_relatorios_page():
        relatorios = obter_relatorios_reabertura()
        relatorios_selection.options = [
            ft.dropdown.Option(
                str(rel[0]),
                f"{formatar_data_hora(rel[4])} — {'Global' if rel[1] == 'global' else f'{rel[2]} ({rel[3] or 'sem motorista'})'} — {
                    rel[8]} passageiros",
            )
            for rel in relatorios
        ]
        relatorios_selection.value = relatorios_selection.options[
            0].key if relatorios_selection.options else None
        carregar_relatorio_selecionado()

    relatorios_page = ft.Container(
        content=ft.Column([
            ft.Text("Relatórios de Reabertura", size=24,
                    color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Selecione um relatório para visualizar a lista de passageiros correspondente.",
                size=16,
                color=tc(),
            ),
            relatorios_selection,
            relatorios_feedback,
            relatorios_summary,
            relatorios_table,
            ft.Row([
                ft.ElevatedButton(
                    "Atualizar lista",
                    on_click=lambda e: refresh_relatorios_page(),
                    bgcolor=ft.Colors.BLUE,
                    color=ft.Colors.WHITE,
                ),
                ft.ElevatedButton(
                    "Apagar relatório",
                    on_click=excluir_relatorio_selecionado,
                    bgcolor=ft.Colors.RED,
                    color=ft.Colors.WHITE,
                ),
                ft.ElevatedButton(
                    "Apagar todos",
                    on_click=excluir_todos_relatorios,
                    bgcolor=ft.Colors.RED_200,
                    color=ft.Colors.BLACK,
                ),
                ft.ElevatedButton(
                    "Voltar",
                    on_click=go_to_home,
                    bgcolor=ft.Colors.GREY_400,
                    color=ft.Colors.BLACK,
                ),
            ], spacing=10),
        ], spacing=16, scroll=ft.ScrollMode.ADAPTIVE),
        expand=True,
        padding=20,
    )

    notifications_list_container = ft.Column(spacing=12)
    notifications_page = ft.Container(
        content=ft.Column([
            ft.Text("Notificações", size=24, color=ft.Colors.BLUE,
                    weight=ft.FontWeight.BOLD),
            ft.Text(
                "Use o botão abaixo para simular uma notificação e testar o indicador vermelho.",
                size=14,
                color=tc(),
            ),
            ft.Button("Simular notificação",
                      on_click=simulate_notification),
            notifications_list_container,
        ], spacing=16),
        expand=True,
        padding=20,
    )
    refresh_notifications()

    passageiros_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Nome")),
            ft.DataColumn(ft.Text("Veículo")),
            ft.DataColumn(ft.Text("Ida/Volta")),
        ],
        rows=[],
        width=340,
        column_spacing=20,
        heading_text_style=ft.TextStyle(color=tc()),
        data_text_style=ft.TextStyle(color=tc()),
    )

    passageiros_message = ft.Text("", size=14, color=tc())

    def refresh_vehicle_dropdown():
        veiculos = carregar_veiculos()
        options = [
            ft.dropdown.Option(
                veiculo["placa"], f"{veiculo['placa']} ({veiculo['capacidade']} pax)")
            for veiculo in veiculos
        ]
        veiculo_dropdown.options = options
        if options:
            if veiculo_dropdown.value not in [option.key for option in options]:
                veiculo_dropdown.value = options[0].key
        else:
            veiculo_dropdown.value = None
        page.update()

    def atualizar_tabela_passageiros(e=None):
        veiculo_selecionado = veiculo_dropdown.value
        if not veiculo_selecionado:
            passageiros_table.rows = []
            passageiros_message.value = "Nenhum veículo disponível no momento."
            passageiros_message.color = ft.Colors.RED
            page.update()
            return

        dados = obter_entradas_passa(veiculo_selecionado)
        veiculo = get_veiculo(veiculo_selecionado)
        capacidade_max = int(veiculo["capacidade"]) if veiculo else 0

        config = verificar_lista_config()
        if config["status"] != "aberta":
            passageiros_message.value = f"A lista está fechada. Relatório salvo para hoje." if config[
                'fechamento_hora'] else "A lista está fechada."
            passageiros_message.color = ft.Colors.ORANGE
            page.update()
            return

        if dados:
            passageiros_table.rows = [
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(index))),
                    ft.DataCell(ft.Text(row[1])),
                    ft.DataCell(ft.Text(row[2])),
                    ft.DataCell(ft.Text(row[3])),
                ])
                for index, row in enumerate(dados, start=1)
            ]
            passageiros_message.value = f"{len(dados)}/{capacidade_max} passageiro(s) no veículo {veiculo_selecionado}."
            passageiros_message.color = ft.Colors.GREEN
        else:
            passageiros_table.rows = []
            passageiros_message.value = f"Nenhum passageiro no veículo {veiculo_selecionado}."
            passageiros_message.color = ft.Colors.RED

        page.update()

    veiculo_dropdown = ft.Dropdown(
        label="Selecionar Veículo",
        width=340,
        options=[
            ft.dropdown.Option("ABC-1234", "ABC-1234 (40 pax)"),
            ft.dropdown.Option("DEF-5678", "DEF-5678 (50 pax)"),
            ft.dropdown.Option("GHI-9012", "GHI-9012 (35 pax)"),
        ],
        value="ABC-1234",
        border_color=ft.Colors.BLUE,
        text_style=ft.TextStyle(color=tc()),
        label_style=ft.TextStyle(color=tc()),
    )
    veiculo_dropdown.on_change = atualizar_tabela_passageiros

    ida_volta_dropdown = ft.Dropdown(
        label="Ida / Volta",
        width=340,
        options=[
            ft.dropdown.Option("Ida"),
            ft.dropdown.Option("Volta"),
            ft.dropdown.Option("Ida/Volta"),
        ],
        value="Ida",
        border_color=ft.Colors.BLUE,
        text_style=ft.TextStyle(color=tc()),
        label_style=ft.TextStyle(color=tc()),
    )

    passageiros_feedback = ft.Text("", size=14, color=tc())

    def handle_inserir_na_lista(e):
        if user_logado[0] is None:
            passageiros_feedback.value = "Você precisa estar logado para se inscrever."
            passageiros_feedback.color = ft.Colors.RED
            page.update()
            return

        nome = user_logado[0][1]
        veiculo_placa = veiculo_dropdown.value
        ida_volta = ida_volta_dropdown.value

        if not ida_volta:
            passageiros_feedback.value = "Selecione Ida, Volta ou Ida/Volta."
            passageiros_feedback.color = ft.Colors.RED
            page.update()
            return

        sucesso, mensagem = inserir_entrada_passa(
            nome, veiculo_placa, ida_volta)
        passageiros_feedback.value = mensagem
        passageiros_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        atualizar_tabela_passageiros()
        page.update()

    def handle_remover_da_lista(e):
        if user_logado[0] is None:
            passageiros_feedback.value = "Você precisa estar logado para se remover."
            passageiros_feedback.color = ft.Colors.RED
            page.update()
            return

        nome = user_logado[0][1]
        veiculo_placa = veiculo_dropdown.value

        sucesso, mensagem = remover_entrada_passa(nome, veiculo_placa)
        passageiros_feedback.value = mensagem
        passageiros_feedback.color = ft.Colors.GREEN if sucesso else ft.Colors.RED
        atualizar_tabela_passageiros()
        page.update()

    passageiros_page = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("Passageiros do Veículo", size=24,
                                color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD),
                padding=20,
            ),
            ft.Container(
                content=ft.Text(
                    "Lista do Ônibus atual:", size=16, color=ft.Colors.BLACK),
                padding=20,
            ),
            veiculo_dropdown,
            passageiros_table,
            passageiros_message,
            ft.Container(
                content=ft.Text("Gerenciar minha inscrição:",
                                size=16, color=ft.Colors.BLACK),
                padding=ft.Padding.only(top=20),
            ),
            ida_volta_dropdown,
            ft.Row([
                ft.Button(
                    "Inserir na lista",
                    on_click=handle_inserir_na_lista,
                    bgcolor=ft.Colors.GREEN,
                    color=ft.Colors.WHITE,
                    width=150,
                ),
                ft.Button(
                    "Remover da lista",
                    on_click=handle_remover_da_lista,
                    bgcolor=ft.Colors.RED,
                    color=ft.Colors.WHITE,
                    width=150,
                ),
            ], spacing=10),
            passageiros_feedback,
            ft.Button(
                "Atualizar",
                on_click=atualizar_tabela_passageiros,
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                width=150,
            ),
        ], spacing=15, scroll=ft.ScrollMode.ADAPTIVE),
        expand=True,
        padding=20,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    atualizar_tabela_passageiros()

    def map_bgcolor():
        return ft.Colors.BLACK if theme_dark[0] else ft.Colors.WHITE

    def map_border_color():
        return ft.Colors.WHITE if theme_dark[0] else ft.Colors.BLUE_100

    def carregar_mapa_caruaru():
        mapa_local = os.path.join(
            os.path.dirname(__file__), "mapa_caruaru.png")
        return mapa_local

    def set_map_info(text):
        mapa_info_text.value = text
        page.update()

    def create_map_marker(label, top, left, color, descricao):
        return ft.Container(
            content=ft.Container(
                content=ft.Text(label, size=10, color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                bgcolor=color,
                border_radius=15,
                padding=ft.Padding.symmetric(horizontal=6, vertical=3),
            ),
            top=top,
            left=left,
            width=90,
            height=25,
            on_click=lambda e, texto=descricao: set_map_info(texto),
        )

    def create_bus_marker(top, left, descricao):
        return ft.Container(
            content=ft.Icon(ft.Icons.DIRECTIONS_BUS,
                            color=ft.Colors.BLACK, size=20),
            bgcolor=ft.Colors.YELLOW,
            width=34,
            height=34,
            border_radius=17,
            top=top,
            left=left,
            border=ft.Border.all(1, ft.Colors.BLACK),
            on_click=lambda e, texto=descricao: set_map_info(texto),
        )

    mapa_error_content = ft.Container(
        content=ft.Text(
            "Não foi possível carregar o mapa. Verifique sua conexão de internet.",
            size=16,
            color=ft.Colors.RED,
        ),
        padding=20,
        alignment=ft.Alignment.CENTER,
        bgcolor=map_bgcolor(),
    )
    mapa_image = ft.Image(
        src=carregar_mapa_caruaru(),
        width=700,
        height=500,
        fit=ft.BoxFit.CONTAIN,
        error_content=mapa_error_content,
    )

    mapa_viewer_content = ft.Container(
        content=ft.Stack([
            mapa_image,
            create_map_marker("Centro", 185, 250, ft.Colors.RED,
                              "Ponto selecionado: Centro — parada principal"),
            create_map_marker("Universidade", 125, 500, ft.Colors.BLUE,
                              "Ponto selecionado: Universidade — parada acadêmica"),
            create_map_marker("Terminal", 270, 270, ft.Colors.GREEN,
                              "Ponto selecionado: Terminal — ponto final"),
            create_bus_marker(240, 370,
                              "Ônibus atual — posição simulada no mapa"),
        ]),
        width=700,
        height=500,
        bgcolor=map_bgcolor(),
        alignment=ft.Alignment.CENTER,
    )

    mapa_subtitle_text = ft.Text(
        "Mapa interativo da cidade de Caruaru. Use o zoom e arraste para explorar.",
        size=15,
        color=tc(),
        text_align=ft.TextAlign.CENTER,
    )
    mapa_info_text = ft.Text(
        "Selecione um ponto no mapa ou o ônibus para ver detalhes.",
        size=13,
        color=tc(),
        text_align=ft.TextAlign.CENTER,
    )

    legenda_principal_text = ft.Text(
        "Centro — parada principal", size=12, color=tc(), text_align=ft.TextAlign.LEFT)
    legenda_universidade_text = ft.Text(
        "Universidade — parada acadêmica", size=12, color=tc(), text_align=ft.TextAlign.LEFT)
    legenda_onibus_text = ft.Text(
        "Ônibus atual — posição simulada", size=12, color=tc(), text_align=ft.TextAlign.LEFT)

    legenda_container = ft.Container(
        content=ft.Column([
            ft.Text("Legenda do mapa", size=14,
                    weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE, text_align=ft.TextAlign.CENTER),
            ft.Divider(color=ft.Colors.GREY_400),
            ft.Row([
                ft.Container(width=12, height=12,
                             bgcolor=ft.Colors.RED, border_radius=6),
                legenda_principal_text,
            ], spacing=6, alignment=ft.MainAxisAlignment.START),
            ft.Row([
                ft.Container(width=12, height=12,
                             bgcolor=ft.Colors.BLUE, border_radius=6),
                legenda_universidade_text,
            ], spacing=6, alignment=ft.MainAxisAlignment.START),
            ft.Row([
                ft.Container(width=12, height=12,
                             bgcolor=ft.Colors.YELLOW, border_radius=6),
                legenda_onibus_text,
            ], spacing=6, alignment=ft.MainAxisAlignment.START),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.START),
        width=200,
        padding=10,
        border_radius=8,
        border=ft.Border.all(1, map_border_color()),
        bgcolor=map_bgcolor(),
    )

    mapa_container = ft.Container(
        content=ft.Column([
            ft.Text("Mapa de Caruaru", size=24,
                    color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD),
            mapa_subtitle_text,
            ft.Row([
                legenda_container,
                ft.Container(
                    content=ft.InteractiveViewer(
                        content=mapa_viewer_content,
                        min_scale=0.5,
                        max_scale=3,
                        align=ft.Alignment.CENTER,
                    ),
                    width=700,
                    height=500,
                    bgcolor=map_bgcolor(),
                    padding=0,
                    border_radius=10,
                    border=ft.Border.all(1, map_border_color()),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20, expand=True),
            mapa_info_text,
        ], alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        ),
        padding=20,
        expand=True,
        bgcolor=map_bgcolor(),
    )

    barra_nav = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Home"),
            ft.NavigationBarDestination(
                icon=ft.Icons.LOCATION_ON_ROUNDED, label="Mapa")
        ],
        selected_index=0,
        bgcolor=ft.Colors.BLUE,
        indicator_color=ft.Colors.WHITE,
        on_change=mudanca_nav,
    )

    main_container = ft.Container(content=login_container, expand=True)

    page.add(
        ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Image(src="IMG_3801.PNG", width=100, height=100),
                welcome_text,
                main_container
            ]
        )
    )

    async def _auto_verificar_fechamento():
        while True:
            try:
                # verificar_lista_config já fecha a lista quando necessário
                changed = False
                before = carregar_lista_config()
                verificar_lista_config()
                after = carregar_lista_config()
                if before.get("status") != after.get("status") or before.get("fechamento_hora") != after.get("fechamento_hora"):
                    changed = True
                    print(f"[DEBUG] Lista global mudou: {before} -> {after}")

                # checar configs por veículo
                veiculos = carregar_veiculos()
                for v in veiculos:
                    placa = v.get("placa")
                    b = carregar_lista_config_veiculo(placa)
                    verificar_lista_config_veiculo(placa)
                    a = carregar_lista_config_veiculo(placa)
                    if b.get("status") != a.get("status") or b.get("fechamento_hora") != a.get("fechamento_hora"):
                        changed = True
                        print(f"[DEBUG] Lista {placa} mudou: {b} -> {a}")

                # se houve mudança, atualiza a UI relevante
                if changed:
                    print("[DEBUG] Atualizando UI...")
                    try:
                        refresh_admin_panel()
                    except Exception as ex:
                        print(f"[DEBUG] Erro em refresh_admin_panel: {ex}")
                    try:
                        atualizar_tabela_passageiros()
                    except Exception as ex:
                        print(
                            f"[DEBUG] Erro em atualizar_tabela_passageiros: {ex}")
                    try:
                        page.update()
                    except Exception as ex:
                        print(f"[DEBUG] Erro em page.update: {ex}")
            except Exception as ex:
                print(f"[DEBUG] Erro geral: {ex}")
            await asyncio.sleep(2)

    try:
        asyncio.create_task(_auto_verificar_fechamento())
    except Exception:
        # fallback para ambientes sem loop ativo
        pass


ft.run(main)
