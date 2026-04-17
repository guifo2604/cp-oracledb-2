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
    <html>
    <head>
        <title>Teste</title>
    </head>
    <body>
        <h1>Funcionou 🚀</h1>
    </body>
    </html>
    """

app = app



