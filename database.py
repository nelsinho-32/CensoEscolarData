import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 5435))
    dbname = os.getenv("DB_NAME", "censoescolar")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "123456")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )


def criar_tabela(conexao, recriar=True):
    with conexao.cursor() as cursor:
        if recriar:
            cursor.execute("DROP VIEW IF EXISTS instituicoesensino CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS tb_instituicao_ensino CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS instituicoesensino CASCADE;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_instituicao_ensino (
                id SERIAL PRIMARY KEY,
                no_entidade TEXT NOT NULL,
                co_entidade VARCHAR(50) NOT NULL UNIQUE,
                no_uf VARCHAR(100) NOT NULL,
                sg_uf VARCHAR(2) NOT NULL,
                co_uf INTEGER NOT NULL,
                no_municipio TEXT NOT NULL,
                co_municipio INTEGER NOT NULL,
                nu_ano_censo INTEGER NOT NULL,
                qt_mat_bas INTEGER NOT NULL DEFAULT 0,
                qt_mat_inf INTEGER NOT NULL DEFAULT 0,
                qt_mat_fund INTEGER NOT NULL DEFAULT 0,
                qt_mat_med INTEGER NOT NULL DEFAULT 0,
                qt_mat_prof INTEGER NOT NULL DEFAULT 0,
                qt_mat_eja INTEGER NOT NULL DEFAULT 0,
                qt_mat_esp INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP NULL
            );

            CREATE OR REPLACE VIEW instituicoesensino AS 
            SELECT id, no_entidade, co_entidade, no_uf, sg_uf, co_uf, 
                   no_municipio, co_municipio, nu_ano_censo, qt_mat_bas, 
                   qt_mat_inf, qt_mat_fund, qt_mat_med, qt_mat_prof, 
                   qt_mat_eja, qt_mat_esp, 
                   (CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) AS excluido,
                   created_at, deleted_at
            FROM tb_instituicao_ensino;
        """)
        conexao.commit()
