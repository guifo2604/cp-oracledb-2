import os
import oracledb
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS

load_dotenv()

user_banco=os.getenv("USER")
password_banco=os.getenv("SENHA")
dsn_banco=os.getenv("DSN")

app =Flask(__name__)
CORS(app) # permite o front-end acessar o back!

def executar_cashback():
    try:
        conn = oracledb.connect(
            user=user_banco,
            password=password_banco,
            dsn=dsn_banco
        )

        cursor = conn.cursor()

        plsql_block = """
        DECLARE
        CURSOR c_inscricoes IS
            SELECT ID_INSCRICAO, ID_USUARIO, VALOR_PAGO_INSCRICAO, TIPO
            FROM TB_INSCRICAO
            WHERE STATUS_INSCRICAO = 'PRESENT';

        v_id_inscricao TB_INSCRICAO.ID_INSCRICAO%TYPE;
        v_id_usuario TB_INSCRICAO.ID_USUARIO%TYPE;
        v_valor TB_INSCRICAO.VALOR_PAGO_INSCRICAO%TYPE;
        v_tipo TB_INSCRICAO.TIPO%TYPE;

        total_presencas NUMBER;
        cashback NUMBER;

        v_id_log TB_LOG_AUDITORIA.ID_LOG_AUDITORIA%TYPE;


    BEGIN
        OPEN c_inscricoes;

        LOOP
            FETCH c_inscricoes INTO v_id_inscricao, v_id_usuario, v_valor, v_tipo;
            EXIT WHEN c_inscricoes%NOTFOUND;

            -- Contagem de presenças
            SELECT COUNT(*)
            INTO total_presencas
            FROM TB_INSCRICAO
            WHERE ID_USUARIO = v_id_usuario
            AND STATUS_INSCRICAO = 'PRESENT';

            -- Regra de cashback
            IF total_presencas > 3 THEN
                cashback := v_valor * 0.25;
            ELSIF v_tipo = 'VIP' THEN
                cashback := v_valor * 0.20;
            ELSE
                cashback := v_valor * 0.10;
            END IF;

            -- Atualiza saldo
            UPDATE TB_USUARIO
            SET SALDO_USUARIO = SALDO_USUARIO + cashback
            WHERE ID_USUARIO = v_id_usuario;

            SELECT NVL(MAX(ID_LOG_AUDITORIA),0) + 1
            INTO v_id_log
            FROM TB_LOG_AUDITORIA;

            -- Log
            INSERT INTO TB_LOG_AUDITORIA (
                ID_LOG_AUDITORIA,
                ID_INSCRICAO,
                MOTIVO,
                DATA
            )
            VALUES (
                v_id_log,
                v_id_inscricao,
                'Cashback aplicado',
                SYSDATE
            );
        END LOOP;

        CLOSE c_inscricoes;

        COMMIT;



    END;
    
        """

        cursor.execute(plsql_block)
        conn.commit()
        print("cashback processed sucessed")
    except oracledb.DatabaseError as e:
        error, = e.args
        print(f"Erro oracle: {error.code} - {error.message}")

        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/executar-cashback", methods=["POST"])
def rota_cacshback():
    executar_cashback() # Chama sua função
    return jsonify({"mensagem": "OK"}), 200 # Retorna confirmação para o Front

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    try:
        conn = oracledb.connect(
            user=user_banco,
            password=password_banco,
            dsn=dsn_banco
        )

        cursor = conn.cursor()

        cursor.execute("""
        SELECT 
            U.ID_USUARIO,
            U.NOME_USUARIO,
            U.SALDO_USUARIO,
            NVL(P.PRESENCAS, 0) AS PRESENCAS
        FROM TB_USUARIO U
        LEFT JOIN (
            SELECT ID_USUARIO, COUNT(*) AS PRESENCAS
            FROM TB_INSCRICAO
            WHERE STATUS_INSCRICAO = 'PRESENT'
            GROUP BY ID_USUARIO
        ) P ON U.ID_USUARIO = P.ID_USUARIO
        ORDER BY U.ID_USUARIO
                """)

        usuarios=[]
        for row in cursor:
            usuarios.append({
                "id": row[0],
                "nome": row[1],
                "saldo": float(row[2]) if row[2] else 0,
                "presencas": row[3]
            })
        return jsonify(usuarios)
    except oracledb.DatabaseError as e:
        error, = e.args
        return {"erro": error.message}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route("/")
def home():
    return """
    <!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Cashback - Oracle</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body class="bg-gray-100 min-h-screen">

    <div class="container mx-auto px-4 py-10 max-w-4xl">
        
        <div class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">SISTEMA DE CASHBACK</h1>
                <p class="text-gray-600">Gerenciamento de recompensas via Oracle DB</p>
            </div>
            <button onclick="processarCashback()" id="btnProcessar" 
                class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg flex items-center transition-all">
                <i class="fas fa-coins mr-2"></i>
                <span>Executar Regras de Cashback</span>
            </button>
        </div>

        <div id="alerta" class="hidden mb-6 p-4 rounded-lg flex items-center shadow-sm">
            <i id="alertaIcone" class="mr-3 text-xl"></i>
            <span id="alertaTexto" class="font-medium"></span>
        </div>

        <div class="bg-white rounded-xl shadow-md overflow-hidden">
            <div class="p-6 border-b border-gray-200 bg-gray-50 flex items-center">
                <i class="fas fa-users text-blue-600 mr-2"></i>
                <h2 class="text-xl font-semibold text-gray-700">Usuários e Saldos</h2>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-100 text-gray-600 uppercase text-sm leading-normal">
                            <th class="py-3 px-6 border-b">ID</th>
                            <th class="py-3 px-6 border-b">Nome</th>
                             <th class="py-3 px-6 border-b text-center">Presença</th>
                            <th class="py-3 px-6 border-b text-right">Saldo Atual</th>
                        </tr>
                    </thead>
                    <tbody id="tabelaCorpo" class="text-gray-700 text-sm font-light">
                        </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const API_URL = "";

        // Função para buscar usuários
        async function buscarUsuarios() {
            try {
                const response = await fetch(`${API_URL}/usuarios`);
                const dados = await response.json();
                
                const tabela = document.getElementById('tabelaCorpo');
                tabela.innerHTML = '';

                dados.forEach(user => {
                    const tr = document.createElement('tr');
                    tr.className = "border-b border-gray-200 hover:bg-gray-50 transition-colors";
                    tr.innerHTML = `
                        <td class="py-4 px-6 font-medium">${user.id}</td>
                        <td class="py-4 px-6">${user.nome}</td>
                        <td class="py-4 px-6 text-center font-semibold text-gray-400">
                            ${user.presencas}
                        </td>
                        <td class="py-4 px-6 text-right font-bold text-green-600">
                            R$ ${user.saldo.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </td>
                    `;
                    tabela.appendChild(tr);
                });
            } catch (error) {
                mostrarAlerta("Erro ao conectar com o servidor. O back-end está rodando?", "erro");
            }
        }

        // Função para disparar o cashback
        async function processarCashback() {
            const btn = document.getElementById('btnProcessar');
            const originalContent = btn.innerHTML;
            
            // Estágio de Carregamento
            btn.disabled = true;
            btn.classList.replace('bg-blue-600', 'bg-gray-400');
            btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> Processando...`;

            try {
                const response = await fetch(`${API_URL}/executar-cashback`, { method: 'POST' });
                
                if (response.ok) {
                    mostrarAlerta("Sucesso! Cashback processado no Oracle DB.", "sucesso");
                    buscarUsuarios(); // Atualiza a lista
                } else {
                    mostrarAlerta("Erro no banco de dados ao processar.", "erro");
                }
            } catch (error) {
                mostrarAlerta("Falha na comunicação com a API.", "erro");
            } finally {
                btn.disabled = false;
                btn.classList.replace('bg-gray-400', 'bg-blue-600');
                btn.innerHTML = originalContent;
            }
        }

        // Função para mostrar alertas na tela
        function mostrarAlerta(mensagem, tipo) {
            const alerta = document.getElementById('alerta');
            const texto = document.getElementById('alertaTexto');
            const icone = document.getElementById('alertaIcone');

            alerta.classList.remove('hidden', 'bg-red-100', 'text-red-700', 'bg-green-100', 'text-green-700');

            if (tipo === 'erro') {
                alerta.classList.add('bg-red-100', 'text-red-700');
                icone.className = 'fas fa-exclamation-circle mr-3';
            } else {
                alerta.classList.add('bg-green-100', 'text-green-700');
                icone.className = 'fas fa-check-circle mr-3';
            }

            texto.innerText = mensagem;
            
            setTimeout(() => {
                alerta.classList.add('hidden');
            }, 5000);
        }

        // Carrega os dados ao iniciar a página
        window.onload = buscarUsuarios;
    </script>
</body>
</html>
    """

app = app



