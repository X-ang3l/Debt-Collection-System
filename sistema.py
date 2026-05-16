import customtkinter as ctk
import sqlite3
import os
from datetime import datetime, date, timedelta
from tkinter import messagebox, Toplevel, filedialog
from tkcalendar import DateEntry
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# Configurações Globais de Tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def validar_cpf(cpf: str) -> bool:
    """Valida CPF de forma segura."""
    if not cpf:
        return True  # Vazio é considerado válido (opcional)
    
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    # Validação 1º dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto == 10: 
        resto = 0
    if resto != int(cpf[9]): 
        return False

    # Validação 2º dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto == 10: 
        resto = 0
    if resto != int(cpf[10]): 
        return False

    return True


def format_brl(value: float) -> str:
    """Formata valores em reais com ponto de milhares e vírgula decimal."""
    if value is None:
        return "0,00"
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_brl_number(value: str) -> float:
    """Converte texto brasileiro para float, aceitando 1.234,56 ou 1234.56."""
    if value is None:
        return 0.0
    text = str(value).strip().replace("R$", "").replace(" ", "")
    text = text.replace(".", "").replace(",", ".")
    return float(text) if text else 0.0


def format_date_display(date_str: str) -> str:
    """Converte data ISO para formato brasileiro dd/mm/yyyy."""
    if not date_str:
        return ""
    try:
        return date.fromisoformat(date_str).strftime('%d/%m/%Y')
    except Exception:
        return date_str


def next_month_same_day(date_obj: date) -> date:
    """Retorna a mesma data no próximo mês, ajustando para o último dia se necessário."""
    year = date_obj.year + (date_obj.month // 12)
    month = date_obj.month % 12 + 1
    day = date_obj.day
    while day > 0:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, 1)


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login - Sistema de Cobranças")
        self.geometry("400x250")
        self.resizable(False, False)

        # Centralizar a janela
        self.eval('tk::PlaceWindow . center')

        # Frame principal
        frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Título
        lbl_titulo = ctk.CTkLabel(frame, text="Sistema de Gestão de Cobranças", 
                                font=ctk.CTkFont(size=16, weight="bold"), text_color="#4CC9F0")
        lbl_titulo.pack(pady=(20, 10))

        # Campo de senha
        lbl_senha = ctk.CTkLabel(frame, text="Digite a senha:", text_color="white")
        lbl_senha.pack(pady=(10, 5))

        self.entry_senha = ctk.CTkEntry(frame, placeholder_text="Senha", show="*", height=35, width=250)
        self.entry_senha.pack(pady=(0, 20))
        self.entry_senha.focus()

        # Botão de login
        btn_login = ctk.CTkButton(frame, text="Entrar", command=self.verificar_senha, 
                                fg_color="#3498db", height=40, font=ctk.CTkFont(size=14, weight="bold"))
        btn_login.pack(pady=(0, 20))

        # Bind para Enter
        self.entry_senha.bind("<Return>", lambda x: self.verificar_senha())

    def verificar_senha(self):
        senha = self.entry_senha.get()
        if senha == "leandro6694":
            self.destroy()
            # Iniciar o sistema principal
            app = SistemaCobranca()
            app.mainloop()
        else:
            messagebox.showerror("Erro", "Senha incorreta. Tente novamente.")
            self.entry_senha.delete(0, 'end')
            self.entry_senha.focus()


class SistemaCobranca(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Gestão de Cobranças v5.0 - Refatorizado")
        self.geometry("1400x900")
        self.minsize(1200, 800)

        # Banco de Dados
        self.conn = sqlite3.connect("clientes.db")
        self.cursor = self.conn.cursor()
        self.criar_tabelas()

        # Estado
        self.editando_id = None
        self.clientes_selecionados = set()
        self.mostrando_quitados = False

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._setup_left_frame()
        self._setup_right_frame()
        self.atualizar_visualizacao()

    def _setup_left_frame(self):
        self.frame_esquerdo = ctk.CTkFrame(self, width=420, corner_radius=10, fg_color="#2b2b2b")
        self.frame_esquerdo.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.frame_esquerdo.grid_propagate(False)

        scroll_form = ctk.CTkScrollableFrame(self.frame_esquerdo, fg_color="transparent")
        scroll_form.pack(fill="both", expand=True, padx=0, pady=0)

        lbl_titulo = ctk.CTkLabel(scroll_form, text="Cadastro de Clientes", font=ctk.CTkFont(size=22, weight="bold"), text_color="#4CC9F0", anchor="w")
        lbl_titulo.pack(fill="x", padx=20, pady=20)

        # Campos
        self._create_input(scroll_form, "Nome Completo:", "entry_nome", placeholder="Obrigatório", required=True)
        self._create_input(scroll_form, "CPF (Opcional):", "entry_cpf", placeholder="Apenas números")
        self._create_input(scroll_form, "RG (Opcional):", "entry_rg", placeholder="Apenas números")
        self._create_input(scroll_form, "Endereço (Opcional):", "entry_endereco", placeholder="Rua, Número, Bairro")
        self._create_input(scroll_form, "Celular (Opcional):", "entry_celular", placeholder="DDD + Número")

        frame_taxas = ctk.CTkFrame(scroll_form, fg_color="transparent")
        frame_taxas.pack(fill="x", padx=20, pady=(10, 5))
        
        ctk.CTkLabel(frame_taxas, text="Juros (%):", text_color="white").pack(side="left")
        self.entry_juros = ctk.CTkEntry(frame_taxas, placeholder_text="0.0", width=80, height=35)
        self.entry_juros.pack(side="left", padx=(10, 20))

        ctk.CTkLabel(frame_taxas, text="Multa (%):", text_color="white").pack(side="left")
        self.entry_multa = ctk.CTkEntry(frame_taxas, placeholder_text="0.0", width=80, height=35)
        self.entry_multa.pack(side="left", padx=(10, 0))

        self._create_input(scroll_form, "Valor Inicial da Dívida (R$):", "entry_valor", placeholder="Obrigatório", required=True)
        ctk.CTkLabel(scroll_form, text="Data de Vencimento:", text_color="white").pack(fill="x", padx=20, pady=(10, 5))
        self.entry_data_vencimento = DateEntry(scroll_form, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=30)
        self.entry_data_vencimento.pack(fill="x", padx=20, pady=(0, 10))
        self.entry_data_vencimento.set_date(date.today())

        # Campo Data de Cadastro (Opcional)
        ctk.CTkLabel(scroll_form, text="Data de Cadastro (Opcional):", text_color="white").pack(fill="x", padx=20, pady=(5, 5))
        self.entry_data_cadastro = DateEntry(scroll_form, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=30)
        self.entry_data_cadastro.pack(fill="x", padx=20, pady=(0, 10))
        self.entry_data_cadastro.set_date(date.today())

        self.btn_salvar = ctk.CTkButton(scroll_form, text="Cadastrar / Editar", command=self.salvar_cliente, fg_color="#3498db", height=40, font=ctk.CTkFont(size=14, weight="bold"))
        self.btn_salvar.pack(fill="x", padx=20, pady=10)

        self.btn_cancelar = ctk.CTkButton(scroll_form, text="Cancelar", command=self.limpar_formulario, fg_color="#e74c3c", height=40, state="disabled")
        self.btn_cancelar.pack(fill="x", padx=20, pady=(0, 20))

    def _create_input(self, parent, label_text, attr_name, placeholder="", required=False):
        ctk.CTkLabel(parent, text=label_text, text_color="white").pack(fill="x", padx=20, pady=(10, 5))
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, height=35)
        entry.pack(fill="x", padx=20, pady=(0, 10))
        setattr(self, attr_name, entry)

    def _setup_right_frame(self):
        self.frame_direito = ctk.CTkFrame(self, corner_radius=10, fg_color="#1e1e1e")
        self.frame_direito.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.frame_direito.grid_columnconfigure(0, weight=1)
        # garantir que a linha 2 (onde fica a lista) expanda verticalmente
        self.frame_direito.grid_rowconfigure(2, weight=1)

        frame_topo = ctk.CTkFrame(self.frame_direito, fg_color="transparent")
        frame_topo.grid(row=0, column=0, sticky="ew", padx=15, pady=15)

        self.entry_busca = ctk.CTkEntry(frame_topo, placeholder_text="Busque por Nome, ID ou CPF...", width=250, height=35)
        self.entry_busca.pack(side="left", padx=(0, 10))
        self.entry_busca.bind("<Return>", lambda x: self.atualizar_visualizacao())

        ctk.CTkLabel(frame_topo, text="Vencimento De:", text_color="white").pack(side="left", padx=(10, 5))
        self.cal_data_inicio = DateEntry(frame_topo, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=25, date=date.today())
        self.cal_data_inicio.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(frame_topo, text="Até:", text_color="white").pack(side="left", padx=(10, 5))
        self.cal_data_fim = DateEntry(frame_topo, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=25, date=date.today() + timedelta(days=90))
        self.cal_data_fim.pack(side="left", padx=(0, 10))

        self.btn_filtrar_data = ctk.CTkButton(frame_topo, text="Filtrar", command=self.atualizar_visualizacao, width=100, height=28)
        self.btn_filtrar_data.pack(side="left", padx=(0, 10))

        self.var_filtro_status = ctk.StringVar(value="Todos")
        opcoes_filtro = ["Todos", "Vencidos", "Em dia", "Não Pagaram"]
        self.combo_filtro = ctk.CTkComboBox(frame_topo, variable=self.var_filtro_status, values=opcoes_filtro, width=130, height=35, command=lambda x: self.atualizar_visualizacao())
        self.combo_filtro.pack(side="left")

        frame_acoes = ctk.CTkFrame(self.frame_direito, fg_color="#2b2b2b", corner_radius=8)
        frame_acoes.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        frame_acoes.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.btn_novo = ctk.CTkButton(frame_acoes, text="💳 Contas", command=self.gerenciar_contas, fg_color="#f39c12", height=35)
        self.btn_novo.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.btn_ficha = ctk.CTkButton(frame_acoes, text="📄 Ficha Coleta", command=self.gerar_ficha_coleta, fg_color="#8e44ad", height=35)
        self.btn_ficha.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.btn_historico = ctk.CTkButton(frame_acoes, text="📜 Histórico", command=self.mostrar_historico, fg_color="#e67e22", height=35)
        self.btn_historico.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        self.btn_quitados = ctk.CTkButton(frame_acoes, text="✅ Quitados", command=self.toggle_quitados, fg_color="#27ae60", height=35)
        self.btn_quitados.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

        self.scroll_frame = ctk.CTkScrollableFrame(self.frame_direito, label_text="Lista de Clientes", fg_color="transparent")
        # ocupar todo o espaço disponível sem padding inferior
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 0))

        self.lbl_total_divida = ctk.CTkLabel(self.scroll_frame, text="Total Geral: R$ 0,00", font=ctk.CTkFont(weight="bold", size=14), text_color="white")
        self.lbl_total_divida.pack(fill="x", padx=5, pady=(10, 5))

        self.lista_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.lista_container.pack(fill="both", expand=True, padx=5, pady=(0, 0))

    def criar_tabelas(self):
        """Cria as tabelas necessárias no banco de dados."""
        # Criar tabela clientes (inclui data_cadastro e data_reagendamento)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cpf TEXT UNIQUE,
                rg TEXT UNIQUE,
                endereco TEXT,
                celular TEXT,
                divida REAL DEFAULT 0.0,
                data_vencimento TEXT,
                taxa_juros REAL DEFAULT 0.0,
                taxa_multa REAL DEFAULT 0.0,
                data_cadastro TEXT,
                data_reagendamento TEXT,
                pagou_neste_periodo INTEGER DEFAULT 0
            )
        """)
        
        # Tentar adicionar colunas de migração se estiver atualizando versão antiga
        try:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN pagou_neste_periodo INTEGER DEFAULT 0")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        try:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN data_cadastro TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        try:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN data_reagendamento TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Coluna já existe
        
        # Criar tabela histórico
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                tipo TEXT,
                valor REAL,
                novo_saldo REAL,
                data_transacao TEXT,
                descricao TEXT,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            )
        """)
        
        # Criar tabela contas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                data_vencimento TEXT NOT NULL,
                paga INTEGER DEFAULT 0,
                data_criacao TEXT
            )
        """)
        self.conn.commit()

    def limpar_formulario(self):
        fields = ['entry_nome', 'entry_cpf', 'entry_rg', 'entry_endereco', 'entry_celular', 'entry_juros', 'entry_multa', 'entry_valor']
        for field in fields:
            getattr(self, field).delete(0, 'end')
        # Reset datas para hoje
        try:
            self.entry_data_cadastro.set_date(date.today())
        except Exception:
            pass
        try:
            self.entry_data_vencimento.set_date(date.today())
        except Exception:
            pass
        self.editando_id = None
        self.btn_salvar.configure(text="Cadastrar / Editar")
        self.btn_cancelar.configure(state="disabled")

    def salvar_cliente(self):
        """Salva ou atualiza um cliente no banco de dados."""
        nome = self.entry_nome.get().strip()
        cpf = self.entry_cpf.get().strip()
        rg = self.entry_rg.get().strip()
        endereco = self.entry_endereco.get().strip()
        celular = self.entry_celular.get().strip()
        
        try:
            juros = parse_brl_number(self.entry_juros.get() or "0")
            multa = parse_brl_number(self.entry_multa.get() or "0")
            divida = parse_brl_number(self.entry_valor.get() or "0")
        except ValueError:
            messagebox.showerror("Erro", "Verifique os valores numéricos (juros, multa e dívida).")
            return

        # Validações Obrigatórias
        if not nome:
            messagebox.showwarning("Atenção", "Nome é obrigatório.")
            return
        if divida < 0:
            messagebox.showwarning("Atenção", "Valor da dívida não pode ser negativo.")
            return
        if not hasattr(self, 'entry_data_vencimento'):
            messagebox.showwarning("Atenção", "Data de vencimento é obrigatória.")
            return

        if cpf and not validar_cpf(cpf):
            messagebox.showerror("Erro", "CPF inválido.")
            return

        if juros < 0 or juros > 100:
            messagebox.showwarning("Atenção", "Taxa de juros deve estar entre 0 e 100%.")
            return

        if multa < 0 or multa > 100:
            messagebox.showwarning("Atenção", "Taxa de multa deve estar entre 0 e 100%.")
            return
        
        # Normalização de CPF/RG para evitar erro com None
        cpf_db = cpf if cpf else None
        rg_db = rg if rg else None
        try:
            data_vencimento = self.entry_data_vencimento.get_date().isoformat()
        except Exception:
            data_vencimento = date.today().isoformat()

        try:
            if self.editando_id:
                # Atualização
                # capturar data de cadastro
                data_cadastro = self.entry_data_cadastro.get_date().isoformat() if hasattr(self, 'entry_data_cadastro') else None
                self.cursor.execute("""
                    UPDATE clientes 
                    SET nome=?, cpf=?, rg=?, endereco=?, celular=?,
                        divida=?, data_vencimento=?, taxa_juros=?, taxa_multa=?, data_cadastro=?
                    WHERE id=?
                """, (nome, cpf_db, rg_db, endereco, celular, divida, data_vencimento, juros, multa, data_cadastro, self.editando_id))
                
                self.cursor.execute("""
                    INSERT INTO historico (cliente_id, tipo, valor, novo_saldo, data_transacao, descricao) 
                    VALUES (?, 'Edição', 0, ?, ?, ?)
                """, (self.editando_id, divida, datetime.now().strftime('%Y-%m-%d %H:%M'), 
                      f"Dados atualizados - Saldo: R$ {format_brl(divida)}"))
                
                msg_sucesso = "Cliente atualizado com sucesso!"
                self.editando_id = None
            else:
                # Inserção - Verificação de Duplicidade
                if cpf_db:
                    self.cursor.execute("SELECT id FROM clientes WHERE cpf=?", (cpf_db,))
                    if self.cursor.fetchone():
                        messagebox.showerror("Erro", "CPF já cadastrado!")
                        return
                
                if rg_db:
                    self.cursor.execute("SELECT id FROM clientes WHERE rg=?", (rg_db,))
                    if self.cursor.fetchone():
                        messagebox.showerror("Erro", "RG já cadastrado!")
                        return

                # capturar data de cadastro
                data_cadastro = self.entry_data_cadastro.get_date().isoformat() if hasattr(self, 'entry_data_cadastro') else None
                self.cursor.execute("""
                    INSERT INTO clientes (nome, cpf, rg, endereco, celular, divida, data_vencimento, taxa_juros, taxa_multa, data_cadastro, pagou_neste_periodo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (nome, cpf_db, rg_db, endereco, celular, divida, data_vencimento, juros, multa, data_cadastro))
                
                novo_id = self.cursor.lastrowid
                self.cursor.execute("""
                    INSERT INTO historico (cliente_id, tipo, valor, novo_saldo, data_transacao, descricao) 
                    VALUES (?, 'Cadastro Inicial', ?, ?, ?, ?)
                """, (novo_id, divida, divida, datetime.now().strftime('%Y-%m-%d %H:%M'), 
                      f"Cliente registrado com dívida inicial de R$ {format_brl(divida)}"))
                
                msg_sucesso = "Cliente cadastrado com sucesso!"

            self.conn.commit()
            self.limpar_formulario()
            self.atualizar_visualizacao()
            messagebox.showinfo("Sucesso", msg_sucesso)

        except sqlite3.IntegrityError as e:
            messagebox.showerror("Erro de Banco de Dados", 
                               f"Erro de integridade: {e}\nVerifique se CPF/RG não estão duplicados.")
        except Exception as e:
            messagebox.showerror("Erro Crítico", f"Ocorreu um erro inesperado: {e}")
            print(f"Debug: {e}")

    def atualizar_visualizacao(self):
        """Recria a lista de clientes com base nos filtros de data e status."""
        # Limpar lista anterior
        for widget in self.lista_container.winfo_children():
            widget.destroy()

        # Coletar filtros
        data_inicio_str = self.cal_data_inicio.get_date().isoformat()
        data_fim_str = self.cal_data_fim.get_date().isoformat()
        status_filtro = self.var_filtro_status.get()
        busca = self.entry_busca.get().lower().strip()

        # Construir Query Dinâmica
        query = """
            SELECT id, nome, cpf, rg, endereco, celular, divida, data_vencimento, taxa_juros, taxa_multa, data_cadastro, data_reagendamento, pagou_neste_periodo
            FROM clientes 
            WHERE 1=1
        """
        params = []

        # Filtro de Busca
        if busca:
            query += " AND (LOWER(nome) LIKE ? OR LOWER(cpf) LIKE ? OR CAST(id AS TEXT) = ?)"
            params.extend([f"%{busca}%", f"%{busca}%", busca])

        # Filtro de Data (Vencimento entre X e Y)
        query += " AND data_vencimento >= ? AND data_vencimento <= ?"
        params.extend([data_inicio_str, data_fim_str])

        try:
            self.cursor.execute(query, params)
            clientes = self.cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Erro SQL", f"Falha na consulta: {e}")
            return

        hoje = date.today()

        # Rolar vencimento para o mês seguinte apenas se o cliente pagou neste período
        try:
            self.cursor.execute(
                "SELECT id, data_vencimento FROM clientes WHERE divida > 0.001 AND pagou_neste_periodo = 1"
            )
            clientes_para_rolar = self.cursor.fetchall()
            for cid, venc in clientes_para_rolar:
                try:
                    venc_dt = date.fromisoformat(venc)
                    if venc_dt < hoje:
                        nova_data_venc = next_month_same_day(venc_dt)
                        self.cursor.execute(
                            "UPDATE clientes SET data_vencimento=?, pagou_neste_periodo=0 WHERE id=?",
                            (nova_data_venc.isoformat(), cid)
                        )
                except Exception:
                    pass
            self.conn.commit()
        except sqlite3.Error:
            pass

        # Filtragem de Status e Quitados
        clientes_filtrados = []
        for cliente in clientes:
            c_id, c_nome, c_cpf, c_rg, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_cadastro, c_reagend, c_pagou = cliente
            venc_dt = date.fromisoformat(c_venc)
            
            # Determinar status
            if c_div <= 0.001:
                status_cliente = "quitado"
            elif venc_dt < hoje:
                status_cliente = "vencido"
            else:
                status_cliente = "em_dia"

            # Se mostrando quitados, mostrar só quitados; senão, mostrar não-quitados
            if self.mostrando_quitados:
                if status_cliente != "quitado":
                    continue
            else:
                if status_cliente == "quitado":
                    continue

            # Aplicar filtro de status
            if status_filtro == "Todos":
                clientes_filtrados.append(cliente)
            elif status_filtro == "Vencidos" and status_cliente == "vencido":
                clientes_filtrados.append(cliente)
            elif status_filtro == "Em dia" and status_cliente == "em_dia":
                clientes_filtrados.append(cliente)
            elif status_filtro == "Não Pagaram" and (not c_pagou) and c_div > 0.001:
                clientes_filtrados.append(cliente)

        # Ordenação: Por Endereço (se vazio, usa Nome), depois por Nome
        clientes_filtrados.sort(key=lambda x: (
            (x[4] or x[1]).upper() if x[4] else x[1].upper()
        ))

        # Renderização na Interface
        total_divida = 0.0
        
        for cliente in clientes_filtrados:
            c_id, c_nome, c_cpf, c_rg, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_cadastro, c_reagend, c_pagou = cliente
            
            # Cálculo de Juros/Multa se vencido
            valor_exibicao = c_div
            cor_divida = "#FFFFFF"  # Branco
            status_text = "Em dia"
            cor_status = "#2ecc71"  # Verde

            if c_div > 0.001:
                venc_dt = date.fromisoformat(c_venc)
                if venc_dt < hoje:
                    dias_atraso = (hoje - venc_dt).days
                    # Cálculo de juros simples
                    juros_val = c_div * (c_juros / 100) * (dias_atraso / 30)
                    multa_val = c_div * (c_multa / 100)
                    valor_exibicao = c_div + juros_val + multa_val
                    status_text = f"Vencido ({dias_atraso} dias)"
                    cor_divida = "#e74c3c"  # Vermelho
                    cor_status = "#e74c3c"
            
            total_divida += valor_exibicao

            # Criar Frame do Cliente
            frame_cliente = ctk.CTkFrame(self.lista_container, fg_color="#2b2b2b", corner_radius=8, height=60)
            frame_cliente.pack(fill="x", pady=4, padx=5)
            frame_cliente.grid_columnconfigure(0, weight=1)  # Nome/Endereço
            frame_cliente.grid_columnconfigure(1, weight=0)  # Valor
            frame_cliente.grid_columnconfigure(2, weight=0)  # Botões

            # Info Principal (Nome e Endereço)
            lbl_info = ctk.CTkFrame(frame_cliente, fg_color="transparent")
            lbl_info.grid(row=0, column=0, sticky="w", padx=15, pady=10)
            
            # Status de pagamento
            status_pagamento = "✅ Pagou esse mês" if c_pagou else "⚠️ Não pagou nenhum valor ainda"
            cor_pagamento = "#27ae60" if c_pagou else "#e74c3c"
            
            lbl_nome_frame = ctk.CTkFrame(lbl_info, fg_color="transparent")
            lbl_nome_frame.pack(anchor="w")
            
            lbl_nome = ctk.CTkLabel(lbl_nome_frame, text=c_nome, font=ctk.CTkFont(size=14, weight="bold"), 
                                   text_color="white", anchor="w")
            lbl_nome.pack(side="left", anchor="w")
            
            lbl_status_pag = ctk.CTkLabel(lbl_nome_frame, text=status_pagamento, 
                                         font=ctk.CTkFont(size=10), text_color=cor_pagamento)
            lbl_status_pag.pack(side="left", padx=(10, 0))
            
            info_text = f"{c_end or 'S/endereço'}"
            if c_cel:
                info_text += f" | {c_cel}"
            lbl_end = ctk.CTkLabel(lbl_info, text=info_text, font=ctk.CTkFont(size=11), 
                                  text_color="#aaaaaa", anchor="w")
            lbl_end.pack(anchor="w")

            # Data de vencimento
            data_venc_display = format_date_display(c_venc)
            if c_reagend:
                data_venc_display = f"Re-agendado: {format_date_display(c_reagend)}"
            lbl_venc = ctk.CTkLabel(lbl_info, text=f"Vencimento: {data_venc_display}", font=ctk.CTkFont(size=9), 
                                  text_color="#ffb347", anchor="w")
            lbl_venc.pack(anchor="w")

            if c_cpf:
                lbl_cpf = ctk.CTkLabel(lbl_info, text=f"CPF: {c_cpf}", font=ctk.CTkFont(size=10), 
                                      text_color="#888888", anchor="w")
                lbl_cpf.pack(anchor="w")

            # Info Financeira (Valor e Status)
            lbl_valor_frame = ctk.CTkFrame(frame_cliente, fg_color="transparent")
            lbl_valor_frame.grid(row=0, column=1, sticky="e", padx=15)

            lbl_status = ctk.CTkLabel(lbl_valor_frame, text=status_text, 
                                     font=ctk.CTkFont(size=10, weight="bold"), text_color=cor_status)
            lbl_status.pack(anchor="e")

            lbl_valor = ctk.CTkLabel(lbl_valor_frame, text=f"R$ {format_brl(valor_exibicao)}", 
                                    font=ctk.CTkFont(size=16, weight="bold"), text_color=cor_divida)
            lbl_valor.pack(anchor="e")

            # Botões de Ação
            btn_frame = ctk.CTkFrame(frame_cliente, fg_color="transparent")
            btn_frame.grid(row=0, column=2, sticky="e", padx=15)

            btn_pag = ctk.CTkButton(btn_frame, text="Pagar", width=70, height=30, 
                                   font=ctk.CTkFont(size=11),
                                   command=lambda id=c_id, val=valor_exibicao, nome=c_nome: 
                                           self.aplicar_pagamento(id, val, nome))
            btn_pag.pack(side="left", padx=2)

            btn_edit = ctk.CTkButton(btn_frame, text="Editar", width=70, height=30, 
                                    font=ctk.CTkFont(size=11),
                                    fg_color="#3498db", hover_color="#2980b9",
                                    command=lambda id=c_id: self.carregar_cliente(id))
            btn_edit.pack(side="left", padx=2)

            btn_del = ctk.CTkButton(btn_frame, text="Excluir", width=70, height=30, 
                                   font=ctk.CTkFont(size=11),
                                   fg_color="#e74c3c", hover_color="#c0392b",
                                   command=lambda id=c_id: self.excluir_cliente(id))
            btn_del.pack(side="left", padx=2)

            btn_reagend = ctk.CTkButton(btn_frame, text="Re-agendar", width=80, height=30,
                                       font=ctk.CTkFont(size=10),
                                       fg_color="#9b59b6", hover_color="#8e44ad",
                                       command=lambda id=c_id, nome=c_nome: self.reagendar_cliente(id, nome))
            btn_reagend.pack(side="left", padx=2)

        # Atualizar total
        total_text = f"Total na Lista: R$ {format_brl(total_divida)}"
        if self.mostrando_quitados:
            total_text += " (Quitados)"
        self.lbl_total_divida.configure(text=total_text)

    def carregar_cliente(self, client_id):
        """Carrega os dados do cliente no formulário para edição."""
        try:
            self.cursor.execute("SELECT * FROM clientes WHERE id=?", (client_id,))
            row = self.cursor.fetchone()
            if row:
                    # Desempacotamento correto da tupla
                    # id(0), nome(1), cpf(2), rg(3), endereco(4), celular(5), divida(6), data_vencimento(7), juros(8), multa(9), data_cadastro(10), pagou(11)
                self.editando_id = row[0]
                
                self.entry_nome.delete(0, 'end')
                self.entry_nome.insert(0, row[1] or "")
                
                self.entry_cpf.delete(0, 'end')
                self.entry_cpf.insert(0, row[2] or "")
                
                self.entry_rg.delete(0, 'end')
                self.entry_rg.insert(0, row[3] or "")
                
                self.entry_endereco.delete(0, 'end')
                self.entry_endereco.insert(0, row[4] or "")
                
                self.entry_celular.delete(0, 'end')
                self.entry_celular.insert(0, row[5] or "")
                
                self.entry_juros.delete(0, 'end')
                self.entry_juros.insert(0, str(row[8] or 0))
                
                self.entry_multa.delete(0, 'end')
                self.entry_multa.insert(0, str(row[9] or 0))
                
                self.entry_valor.delete(0, 'end')
                self.entry_valor.insert(0, format_brl(row[6]))

                # Preencher data de vencimento se existir
                try:
                    if row[7]:
                        try:
                            self.entry_data_vencimento.set_date(date.fromisoformat(row[7]))
                        except Exception:
                            self.entry_data_vencimento.set_date(date.today())
                    else:
                        self.entry_data_vencimento.set_date(date.today())
                except Exception:
                    pass

                # Preencher data de cadastro se existir
                try:
                    if row[10]:
                        try:
                            self.entry_data_cadastro.set_date(date.fromisoformat(row[10]))
                        except Exception:
                            self.entry_data_cadastro.set_date(date.today())
                    else:
                        self.entry_data_cadastro.set_date(date.today())
                except Exception:
                    pass

                self.btn_salvar.configure(text="Atualizar Cliente")
                self.btn_cancelar.configure(state="normal")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível carregar o cliente: {e}")
            print(f"Debug: {e}")

    def aplicar_pagamento(self, client_id, valor_total, nome_cliente):
        """Lógica robusta para aplicar pagamento."""
        # Entrada de valor do usuário
        dialog = Toplevel(self)
        dialog.title(f"Pagar: {nome_cliente}")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        
        ctk.CTkLabel(dialog, text="Valor a Pagar (R$):").pack(pady=20)
        entry_pago = ctk.CTkEntry(dialog, width=200)
        entry_pago.pack(pady=10)
        entry_pago.focus()

        def confirmar_pagamento():
            try:
                valor_pago = parse_brl_number(entry_pago.get())
                if valor_pago <= 0:
                    messagebox.showwarning("Aviso", "O valor deve ser maior que zero.")
                    return

                # Obter saldo atual de forma correta
                self.cursor.execute("SELECT divida FROM clientes WHERE id=?", (client_id,))
                linha = self.cursor.fetchone()
                
                if not linha:
                    messagebox.showerror("Erro", "Cliente não encontrado.")
                    dialog.destroy()
                    return

                divida_atual = linha[0]  # Acesso correto ao primeiro elemento da tupla
                novo_saldo = divida_atual - valor_pago

                if novo_saldo < 0:
                    confirm = messagebox.askyesno("Saldo Negativo", 
                        f"O pagamento excede a dívida.\nDívida: R$ {format_brl(divida_atual)}\nPago: R$ {format_brl(valor_pago)}\n"
                        f"Isso criará um saldo de R$ {format_brl(novo_saldo)}. Deseja prosseguir?")
                    if not confirm:
                        return

                # Atualizar Banco e marcar como pagou neste período, limpar reagendamento
                if novo_saldo < divida_atual:  # Se houve redução na dívida
                    self.cursor.execute("UPDATE clientes SET divida=?, pagou_neste_periodo=1, data_reagendamento=NULL WHERE id=?", (max(0, novo_saldo), client_id))
                else:
                    self.cursor.execute("UPDATE clientes SET divida=?, data_reagendamento=NULL WHERE id=?", (max(0, novo_saldo), client_id))
                
                # Registrar no Histórico
                self.cursor.execute("""
                    INSERT INTO historico (cliente_id, tipo, valor, novo_saldo, data_transacao, descricao)
                    VALUES (?, 'Pagamento', ?, ?, ?, ?)
                """, (client_id, valor_pago, max(0, novo_saldo), datetime.now().strftime('%Y-%m-%d %H:%M'), 
                      f"Pagamento de R$ {format_brl(valor_pago)}"))
                
                self.conn.commit()
                
                status_msg = f"Pagamento de R$ {format_brl(valor_pago)} aplicado com sucesso!\nNovo saldo: R$ {format_brl(max(0, novo_saldo))}"
                if novo_saldo < 0:
                    status_msg += f"\n⚠️ Crédito de R$ {format_brl(abs(novo_saldo))}"
                    
                messagebox.showinfo("Sucesso", status_msg)
                dialog.destroy()
                self.atualizar_visualizacao()

            except ValueError:
                messagebox.showerror("Erro", "Valor inválido. Use números (ex: 150.50).")
            except Exception as e:
                messagebox.showerror("Erro Crítico", f"Erro ao processar pagamento: {e}")
                print(f"Debug: {e}")

        ctk.CTkButton(dialog, text="Confirmar", command=confirmar_pagamento).pack(pady=20)

    def excluir_cliente(self, client_id):
        """Exclui um cliente e todo seu histórico de forma segura."""
        # Buscar dados do cliente
        self.cursor.execute("SELECT nome FROM clientes WHERE id=?", (client_id,))
        result = self.cursor.fetchone()
        
        if not result:
            messagebox.showerror("Erro", "Cliente não encontrado.")
            return

        nome_cliente = result[0]
        
        if messagebox.askyesno("Confirmar Exclusão", 
                              f"Tem certeza que deseja excluir '{nome_cliente}' e todo o histórico?\n\nEsta ação não pode ser desfeita!"):
            try:
                self.cursor.execute("DELETE FROM historico WHERE cliente_id=?", (client_id,))
                self.cursor.execute("DELETE FROM clientes WHERE id=?", (client_id,))
                self.conn.commit()
                messagebox.showinfo("Sucesso", f"Cliente '{nome_cliente}' excluído com sucesso.")
                self.atualizar_visualizacao()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível excluir: {e}")
                print(f"Debug: {e}")

    def reagendar_cliente(self, client_id, nome_cliente):
        """Re-agenda um cliente para uma data futura."""
        dialog = Toplevel(self)
        dialog.title(f"Re-agendar: {nome_cliente}")
        dialog.geometry("350x150")
        dialog.resizable(False, False)
        
        ctk.CTkLabel(dialog, text="Data de Re-agendamento:", font=ctk.CTkFont(size=12)).pack(pady=10)
        cal_reagend = DateEntry(dialog, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=30)
        cal_reagend.pack(pady=10)
        cal_reagend.set_date(date.today())

        def confirmar_reagendamento():
            try:
                data_reagend = cal_reagend.get_date().isoformat()
                self.cursor.execute("UPDATE clientes SET data_reagendamento=? WHERE id=?", (data_reagend, client_id))
                self.conn.commit()
                messagebox.showinfo("Sucesso", f"Cliente re-agendado para {cal_reagend.get_date().strftime('%d/%m/%Y')}")
                dialog.destroy()
                self.atualizar_visualizacao()
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao re-agendar: {e}")

        ctk.CTkButton(dialog, text="Confirmar", command=confirmar_reagendamento).pack(pady=10)

    def gerar_ficha_coleta(self):
        """Gera um relatório em PDF com os clientes em cobração."""
        hoje = date.today().isoformat()
        self.cursor.execute("""
            SELECT id, nome, cpf, endereco, celular, divida, data_vencimento, taxa_juros, taxa_multa, data_reagendamento
            FROM clientes WHERE divida > 0.001 AND pagou_neste_periodo = 0
            ORDER BY endereco, nome
        """)
        clientes_bruto = self.cursor.fetchall()
        
        # Filtrar: incluir apenas se data_reagendamento é hoje ou se não há reagendamento
        clientes = []
        for cliente in clientes_bruto:
            c_id, c_nome, c_cpf, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_reagend = cliente
            if c_reagend:
                # Se tem reagendamento, incluir só se for hoje
                if c_reagend == hoje:
                    clientes.append((c_id, c_nome, c_cpf, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_reagend))
            else:
                # Se não tem reagendamento, incluir normalmente
                clientes.append((c_id, c_nome, c_cpf, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_reagend))

        if not clientes:
            messagebox.showinfo("Aviso", "Nenhum cliente em aberto para gerar ficha.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"Ficha_Coleta_{date.today().strftime('%d_%m_%Y')}.pdf"
        )

        if not file_path:
            return

        try:
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4
            
            # Cabeçalho
            c.setFont("Helvetica-Bold", 16)
            c.drawString(cm, height - cm, "FICHA DE COBRAÇÃO")
            c.setFont("Helvetica", 10)
            c.drawString(cm, height - 1.5*cm, f"Data: {date.today().strftime('%d/%m/%Y')}")
            
            # Linha separadora
            c.line(cm, height - 1.7*cm, width - cm, height - 1.7*cm)
            
            y = height - 2.2*cm
            total_divida = 0

            for idx, cliente in enumerate(clientes, 1):
                c_id, c_nome, c_cpf, c_end, c_cel, c_div, c_venc, c_juros, c_multa, c_reagend = cliente
                
                # Usar data_reagendamento se existir, senão usar data_vencimento
                data_usar = c_reagend if c_reagend else c_venc
                
                # Calcular multa/juros se vencido
                valor_total = c_div
                venc_dt = date.fromisoformat(data_usar)
                if venc_dt < date.today():
                    dias_atraso = (date.today() - venc_dt).days
                    juros_val = c_div * (c_juros / 100) * (dias_atraso / 30)
                    multa_val = c_div * (c_multa / 100)
                    valor_total = c_div + juros_val + multa_val

                total_divida += valor_total

                # Endereço em negrito e maior acima do nome
                if c_end:
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(cm, y, f"ENDEREÇO: {c_end}")
                    y -= 0.5*cm

                # Corpo do documento
                c.setFont("Helvetica-Bold", 10)
                c.drawString(cm, y, f"{idx}. {c_nome}")
                
                c.setFont("Helvetica", 9)
                y -= 0.4*cm
                if c_cpf:
                    c.drawString(1.5*cm, y, f"CPF: {c_cpf}")
                    y -= 0.3*cm
                if c_cel:
                    c.drawString(1.5*cm, y, f"Telefone: {c_cel}")
                    y -= 0.3*cm
                
                c.drawString(1.5*cm, y, f"Valor: R$ {format_brl(valor_total)} | Vencimento: {format_date_display(data_usar)}")
                y -= 0.5*cm

                # Quebra de página se necessário
                if y < 2*cm:
                    c.showPage()
                    y = height - cm

            # Rodapé com total
            c.line(cm, y - 0.2*cm, width - cm, y - 0.2*cm)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(cm, y - 0.6*cm, f"TOTAL A COBRAR: R$ {format_brl(total_divida)}")

            c.save()
            messagebox.showinfo("Sucesso", f"Ficha de cobração gerada em:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar PDF: {e}")
            print(f"Debug: {e}")

    def mostrar_historico(self):
        """Mostra o histórico de transações de um cliente."""
        # Criar janela de seleção
        dialog = Toplevel(self)
        dialog.title("Histórico de Cliente")
        dialog.geometry("400x300")

        ctk.CTkLabel(dialog, text="Selecione um cliente:", font=ctk.CTkFont(size=12)).pack(pady=10)

        # Buscar clientes
        self.cursor.execute("SELECT id, nome FROM clientes ORDER BY nome")
        clientes_list = self.cursor.fetchall()

        if not clientes_list:
            messagebox.showwarning("Aviso", "Nenhum cliente cadastrado.")
            dialog.destroy()
            return

        cliente_map = {f"{c[1]} (ID: {c[0]})": c[0] for c in clientes_list}
        combo_clientes = ctk.CTkComboBox(dialog, values=list(cliente_map.keys()), width=350)
        combo_clientes.pack(pady=10, padx=20)

        def mostrar_transacoes():
            sel = combo_clientes.get()
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um cliente.")
                return

            cliente_id = cliente_map[sel]
            
            # Buscar histórico
            self.cursor.execute("""
                SELECT data_transacao, tipo, valor, novo_saldo, descricao
                FROM historico
                WHERE cliente_id=?
                ORDER BY data_transacao DESC
            """, (cliente_id,))
            
            historico = self.cursor.fetchall()

            if not historico:
                messagebox.showinfo("Aviso", "Nenhuma transação registrada para este cliente.")
                return

            # Criar nova janela com histórico
            hist_window = Toplevel(dialog)
            hist_window.title(f"Histórico - {sel}")
            hist_window.geometry("700x500")

            # ScrollableFrame para o histórico
            scroll_frame = ctk.CTkScrollableFrame(hist_window)
            scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Cabeçalho
            header = ctk.CTkFrame(scroll_frame, fg_color="#3b3b3b")
            header.pack(fill="x", padx=5, pady=5)

            for col, width in [("Data", 100), ("Tipo", 100), ("Valor", 80), ("Saldo", 80)]:
                ctk.CTkLabel(header, text=col, font=ctk.CTkFont(weight="bold"), width=width).pack(side="left", padx=10)

            # Dados
            for transacao in historico:
                data, tipo, valor, saldo, desc = transacao
                row = ctk.CTkFrame(scroll_frame, fg_color="#2b2b2b")
                row.pack(fill="x", padx=5, pady=2)

                ctk.CTkLabel(row, text=data, width=100).pack(side="left", padx=10)
                ctk.CTkLabel(row, text=tipo, width=100).pack(side="left", padx=10)
                ctk.CTkLabel(row, text=f"R$ {format_brl(valor)}", width=80).pack(side="left", padx=10)
                ctk.CTkLabel(row, text=f"R$ {format_brl(saldo)}", width=80).pack(side="left", padx=10)

        ctk.CTkButton(dialog, text="Visualizar Histórico", command=mostrar_transacoes).pack(pady=20)

    def toggle_quitados(self):
        """Alterna entre mostrar clientes em aberto ou quitados."""
        self.mostrando_quitados = not self.mostrando_quitados
        if self.mostrando_quitados:
            self.btn_quitados.configure(fg_color="#e74c3c", text="❌ Voltar ao Aberto")
        else:
            self.btn_quitados.configure(fg_color="#27ae60", text="✅ Ver Quitados")
        self.atualizar_visualizacao()

    def gerenciar_contas(self):
        """Interface para gerenciar contas a pagar do mês."""
        contas_window = Toplevel(self)
        contas_window.title("Gerenciar Contas a Pagar")
        contas_window.geometry("700x600")
        contas_window.resizable(True, True)

        # Frame para adicionar nova conta
        frame_adicionar = ctk.CTkFrame(contas_window, fg_color="#2b2b2b", corner_radius=8)
        frame_adicionar.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(frame_adicionar, text="Adicionar Nova Conta", font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CC9F0").pack(anchor="w", padx=15, pady=(10, 5))

        # Entrada de nome da conta
        ctk.CTkLabel(frame_adicionar, text="Nome da Conta:", text_color="white").pack(anchor="w", padx=15, pady=(10, 5))
        entry_nome_conta = ctk.CTkEntry(frame_adicionar, placeholder_text="Ex: Aluguel, Luz, Água...", height=35)
        entry_nome_conta.pack(fill="x", padx=15, pady=(0, 10))

        # Entrada de data de vencimento
        ctk.CTkLabel(frame_adicionar, text="Data de Vencimento:", text_color="white").pack(anchor="w", padx=15, pady=(5, 5))
        cal_vencimento = DateEntry(frame_adicionar, date_pattern='dd/mm/yyyy', background='darkblue', foreground='white', borderwidth=2, height=30)
        cal_vencimento.pack(anchor="w", padx=15, pady=(0, 10))

        def adicionar_conta():
            nome = entry_nome_conta.get().strip()
            if not nome:
                messagebox.showwarning("Atenção", "Digite o nome da conta.")
                return

            data_venc = cal_vencimento.get_date().isoformat()
            try:
                self.cursor.execute("""
                    INSERT INTO contas (nome, data_vencimento, data_criacao)
                    VALUES (?, ?, ?)
                """, (nome, data_venc, datetime.now().strftime('%Y-%m-%d %H:%M')))
                self.conn.commit()
                entry_nome_conta.delete(0, 'end')
                messagebox.showinfo("Sucesso", "Conta adicionada com sucesso!")
                atualizar_lista_contas()
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao adicionar conta: {e}")

        btn_adicionar = ctk.CTkButton(frame_adicionar, text="➕ Adicionar Conta", command=adicionar_conta, fg_color="#27ae60", height=35)
        btn_adicionar.pack(fill="x", padx=15, pady=(0, 15))

        # Frame para listar contas
        ctk.CTkLabel(contas_window, text="Contas Registradas", font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CC9F0").pack(anchor="w", padx=15, pady=(10, 5))

        scroll_contas = ctk.CTkScrollableFrame(contas_window, fg_color="transparent")
        scroll_contas.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        def atualizar_lista_contas():
            # Limpar lista
            for widget in scroll_contas.winfo_children():
                widget.destroy()

            # Buscar contas
            self.cursor.execute("""
                SELECT id, nome, data_vencimento, paga
                FROM contas
                ORDER BY data_vencimento ASC
            """)
            contas = self.cursor.fetchall()

            if not contas:
                ctk.CTkLabel(scroll_contas, text="Nenhuma conta registrada.", text_color="#aaaaaa", font=ctk.CTkFont(size=12)).pack(pady=20)
                return

            for conta_id, nome_conta, data_venc, paga in contas:
                frame_conta = ctk.CTkFrame(scroll_contas, fg_color="#2b2b2b", corner_radius=8)
                frame_conta.pack(fill="x", pady=5)
                frame_conta.grid_columnconfigure(0, weight=1)

                # Info da conta
                info_frame = ctk.CTkFrame(frame_conta, fg_color="transparent")
                info_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)

                cor_status = "#27ae60" if paga else "#e74c3c"
                status_text = "✅ Paga" if paga else "❌ Pendente"

                ctk.CTkLabel(info_frame, text=nome_conta, font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(anchor="w")
                ctk.CTkLabel(info_frame, text=f"Vencimento: {format_date_display(data_venc)} | Status: {status_text}", font=ctk.CTkFont(size=10), text_color=cor_status).pack(anchor="w")

                # Botões
                btn_frame = ctk.CTkFrame(frame_conta, fg_color="transparent")
                btn_frame.grid(row=0, column=1, sticky="e", padx=15)

                def toggle_paga(cid=conta_id, currentPaga=paga):
                    novo_status = 1 - currentPaga
                    self.cursor.execute("UPDATE contas SET paga=? WHERE id=?", (novo_status, cid))
                    self.conn.commit()
                    atualizar_lista_contas()

                def deletar_conta(cid=conta_id):
                    if messagebox.askyesno("Confirmar", "Deseja excluir esta conta?"):
                        self.cursor.execute("DELETE FROM contas WHERE id=?", (cid,))
                        self.conn.commit()
                        atualizar_lista_contas()

                btn_toggle = ctk.CTkButton(btn_frame, text="Marcar como Paga" if not paga else "Marcar como Pendente", width=150, height=30, 
                                          fg_color="#3498db" if not paga else "#f39c12",
                                          command=toggle_paga)
                btn_toggle.pack(side="left", padx=5)

                btn_del = ctk.CTkButton(btn_frame, text="Excluir", width=70, height=30, fg_color="#e74c3c", command=deletar_conta)
                btn_del.pack(side="left", padx=5)

        # Carregar lista inicial
        atualizar_lista_contas()


if __name__ == "__main__":
    login = LoginWindow()
    login.mainloop()
