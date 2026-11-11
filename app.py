import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "censoescolar.db")
ESCOLA_CSV = os.path.join(BASE_DIR, "microdados_censo_escolar_2025", "dados", "Tabela_Escola_2025.csv")
MATRICULA_CSV = os.path.join(BASE_DIR, "microdados_censo_escolar_2025", "dados", "Tabela_Matricula_2025.csv")

UFS_NORDESTE_SUDESTE = [
    "MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA",
    "MG", "ES", "RJ", "SP"
]

CHUNK_SIZE = 10000


def carregar_matriculas():
    colunas_mat = [
        "CO_ENTIDADE", "QT_MAT_BAS", "QT_MAT_INF", "QT_MAT_FUND",
        "QT_MAT_MED", "QT_MAT_PROF", "QT_MAT_EJA", "QT_MAT_ESP"
    ]
    partes = []
    for chunk in pd.read_csv(
        MATRICULA_CSV,
        sep=";",
        encoding="latin1",
        usecols=colunas_mat,
        chunksize=CHUNK_SIZE
    ):
        partes.append(chunk)

    return pd.concat(partes, ignore_index=True)


def importar_dados():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT co_entidade FROM tb_instituicao_ensino")
    existentes = set(str(row[0]) for row in cursor.fetchall())

    print("Lendo dados de matrículas de forma paginada...")
    df_matriculas = carregar_matriculas()

    colunas_escola = [
        "NU_ANO_CENSO", "NO_REGIAO", "NO_ENTIDADE", "CO_ENTIDADE",
        "NO_UF", "SG_UF", "CO_UF", "NO_MUNICIPIO", "CO_MUNICIPIO"
    ]

    total_inseridos = 0

    print("Importando escolas do Nordeste e Sudeste em lotes...")
    for chunk in pd.read_csv(
        ESCOLA_CSV,
        sep=";",
        encoding="latin1",
        usecols=colunas_escola,
        chunksize=CHUNK_SIZE
    ):
        filtrado = chunk[chunk["SG_UF"].isin(UFS_NORDESTE_SUDESTE)]
        if filtrado.empty:
            continue

        merged = pd.merge(filtrado, df_matriculas, on="CO_ENTIDADE", how="inner")
        if merged.empty:
            continue

        merged = merged[~merged["CO_ENTIDADE"].astype(str).isin(existentes)]
        if merged.empty:
            continue

        registros = [
            (
                str(row.NO_ENTIDADE),
                str(row.CO_ENTIDADE),
                str(row.NO_UF),
                str(row.SG_UF),
                int(row.CO_UF),
                str(row.NO_MUNICIPIO),
                int(row.CO_MUNICIPIO),
                int(row.NU_ANO_CENSO),
                int(row.QT_MAT_BAS),
                int(row.QT_MAT_INF),
                int(row.QT_MAT_FUND),
                int(row.QT_MAT_MED),
                int(row.QT_MAT_PROF),
                int(row.QT_MAT_EJA),
                int(row.QT_MAT_ESP)
            )
            for row in merged.itertuples(index=False)
        ]

        cursor.executemany("""
            INSERT INTO tb_instituicao_ensino (
                no_entidade, co_entidade, no_uf, sg_uf, co_uf,
                no_municipio, co_municipio, nu_ano_censo,
                qt_mat_bas, qt_mat_inf, qt_mat_fund, qt_mat_med,
                qt_mat_prof, qt_mat_eja, qt_mat_esp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, registros)

        conn.commit()
        total_inseridos += len(registros)
        print(f"Lote processado. Total acumulado: {total_inseridos}")

    conn.close()
    print(f"Importação concluída. {total_inseridos} instituições inseridas.")


if __name__ == "__main__":
    importar_dados()
