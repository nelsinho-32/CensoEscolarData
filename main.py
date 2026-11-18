import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from database import get_connection, criar_tabela

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

LOCAIS_DADOS = [
    os.getenv("PASTA_DADOS"),
    BASE_DIR / "microdados_censo_escolar_2025" / "dados",
    BASE_DIR.parent / "CensoEscolarAPI20262" / "microdados_censo_escolar_2025" / "dados",
    BASE_DIR.parent / "microdados_censo_escolar_2025" / "dados",
    BASE_DIR / "dados",
]

PASTA_DADOS = None
for local in LOCAIS_DADOS:
    if local and Path(local).exists():
        PASTA_DADOS = Path(local)
        break

ARQUIVO_CSV_UNIFICADO = PASTA_DADOS / "Tabela_Matricula_2025_V2.csv" if PASTA_DADOS else None
ARQUIVO_ESCOLA = PASTA_DADOS / "Tabela_Escola_2025.csv" if PASTA_DADOS else None
ARQUIVO_MATRICULA = PASTA_DADOS / "Tabela_Matricula_2025.csv" if PASTA_DADOS else None


UFS_PERMITIDAS = [
    "MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA",
    "MG", "ES", "RJ", "SP"
]

COLUNAS = [
    "NO_ENTIDADE",
    "CO_ENTIDADE",
    "NO_UF",
    "SG_UF",
    "CO_UF",
    "NO_MUNICIPIO",
    "CO_MUNICIPIO",
    "NU_ANO_CENSO",
    "QT_MAT_BAS",
    "QT_MAT_INF",
    "QT_MAT_FUND",
    "QT_MAT_MED",
    "QT_MAT_PROF",
    "QT_MAT_EJA",
    "QT_MAT_ESP",
]

MAPEAMENTO = {
    "NO_ENTIDADE": "no_entidade",
    "CO_ENTIDADE": "co_entidade",
    "NO_UF": "no_uf",
    "SG_UF": "sg_uf",
    "CO_UF": "co_uf",
    "NO_MUNICIPIO": "no_municipio",
    "CO_MUNICIPIO": "co_municipio",
    "NU_ANO_CENSO": "nu_ano_censo",
    "QT_MAT_BAS": "qt_mat_bas",
    "QT_MAT_INF": "qt_mat_inf",
    "QT_MAT_FUND": "qt_mat_fund",
    "QT_MAT_MED": "qt_mat_med",
    "QT_MAT_PROF": "qt_mat_prof",
    "QT_MAT_EJA": "qt_mat_eja",
    "QT_MAT_ESP": "qt_mat_esp",
}

CHUNK_SIZE = 10_000


def carregar_matriculas_map():
    colunas_mat = [
        "CO_ENTIDADE", "QT_MAT_BAS", "QT_MAT_INF", "QT_MAT_FUND",
        "QT_MAT_MED", "QT_MAT_PROF", "QT_MAT_EJA", "QT_MAT_ESP"
    ]
    print(f"Carregando dados de matrículas a partir de: {ARQUIVO_MATRICULA}")
    chunks = []
    for chunk in pd.read_csv(
        ARQUIVO_MATRICULA,
        sep=";",
        encoding="latin1",
        usecols=colunas_mat,
        chunksize=CHUNK_SIZE,
        low_memory=False
    ):
        chunks.append(chunk)

    df_matriculas = pd.concat(chunks, ignore_index=True)
    df_matriculas = df_matriculas.drop_duplicates(subset=["CO_ENTIDADE"])
    return df_matriculas


def importar_dados():
    if not PASTA_DADOS or not PASTA_DADOS.exists():
        raise FileNotFoundError(
            f"Pasta com os microdados do Censo Escolar não encontrada.\n"
            f"Locais verificados: {[str(p) for p in LOCAIS_DADOS if p]}"
        )

    conexao = get_connection()
    try:
        criar_tabela(conexao, recriar=True)

        total_importado = 0
        codigos_vistos = set()

        if ARQUIVO_CSV_UNIFICADO and ARQUIVO_CSV_UNIFICADO.exists():
            blocos = pd.read_csv(
                ARQUIVO_CSV_UNIFICADO,
                sep=";",
                encoding="latin1",
                usecols=COLUNAS,
                chunksize=CHUNK_SIZE,
                low_memory=False
            )

            for numero_bloco, df in enumerate(blocos, start=1):
                df = df[df["SG_UF"].isin(UFS_PERMITIDAS)].copy()
                if df.empty:
                    continue

                df = df[COLUNAS]

                repetidos_bloco = df["CO_ENTIDADE"].duplicated(keep=False)
                if repetidos_bloco.any():
                    print("\nCódigos repetidos dentro do bloco:")
                    print(df.loc[repetidos_bloco, ["CO_ENTIDADE", "NO_ENTIDADE", "SG_UF"]].head(20).to_string(index=False))
                    df = df.drop_duplicates(subset=["CO_ENTIDADE"])

                df = df[~df["CO_ENTIDADE"].isin(codigos_vistos)]
                if df.empty:
                    continue

                codigos_vistos.update(df["CO_ENTIDADE"].tolist())
                df = df.rename(columns=MAPEAMENTO)
                df = df.astype(object).where(pd.notna(df), None)

                registros = [
                    tuple(
                        valor.item() if hasattr(valor, "item") else valor
                        for valor in linha
                    )
                    for linha in df.itertuples(index=False, name=None)
                ]

                with conexao.cursor() as cursor:
                    cursor.executemany("""
                        INSERT INTO tb_instituicao_ensino (
                            no_entidade, co_entidade, no_uf, sg_uf, co_uf,
                            no_municipio, co_municipio, nu_ano_censo,
                            qt_mat_bas, qt_mat_inf, qt_mat_fund, qt_mat_med,
                            qt_mat_prof, qt_mat_eja, qt_mat_esp
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (co_entidade) DO NOTHING
                    """, registros)
                conexao.commit()

                total_importado += len(registros)
                print(f"Bloco {numero_bloco}: {len(registros)} instituições inseridas. Total: {total_importado}")

        elif ARQUIVO_ESCOLA and ARQUIVO_ESCOLA.exists() and ARQUIVO_MATRICULA and ARQUIVO_MATRICULA.exists():
            df_matriculas = carregar_matriculas_map()

            colunas_escola = [
                "NU_ANO_CENSO", "NO_REGIAO", "NO_ENTIDADE", "CO_ENTIDADE",
                "NO_UF", "SG_UF", "CO_UF", "NO_MUNICIPIO", "CO_MUNICIPIO"
            ]

            blocos = pd.read_csv(
                ARQUIVO_ESCOLA,
                sep=";",
                encoding="latin1",
                usecols=colunas_escola,
                chunksize=CHUNK_SIZE,
                low_memory=False
            )

            for numero_bloco, chunk in enumerate(blocos, start=1):
                filtrado = chunk[chunk["SG_UF"].isin(UFS_PERMITIDAS)].copy()
                if filtrado.empty:
                    continue

                merged = pd.merge(filtrado, df_matriculas, on="CO_ENTIDADE", how="inner")
                if merged.empty:
                    continue

                merged = merged[COLUNAS]

                repetidos_bloco = merged["CO_ENTIDADE"].duplicated(keep=False)
                if repetidos_bloco.any():
                    merged = merged.drop_duplicates(subset=["CO_ENTIDADE"])

                merged = merged[~merged["CO_ENTIDADE"].isin(codigos_vistos)]
                if merged.empty:
                    continue

                codigos_vistos.update(merged["CO_ENTIDADE"].tolist())
                merged = merged.rename(columns=MAPEAMENTO)
                merged = merged.astype(object).where(pd.notna(merged), None)

                registros = [
                    tuple(
                        valor.item() if hasattr(valor, "item") else valor
                        for valor in linha
                    )
                    for linha in merged.itertuples(index=False, name=None)
                ]

                with conexao.cursor() as cursor:
                    cursor.executemany("""
                        INSERT INTO tb_instituicao_ensino (
                            no_entidade, co_entidade, no_uf, sg_uf, co_uf,
                            no_municipio, co_municipio, nu_ano_censo,
                            qt_mat_bas, qt_mat_inf, qt_mat_fund, qt_mat_med,
                            qt_mat_prof, qt_mat_eja, qt_mat_esp
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (co_entidade) DO NOTHING
                    """, registros)
                conexao.commit()

                total_importado += len(registros)
                print(f"Bloco {numero_bloco}: {len(registros)} instituições inseridas. Total: {total_importado}")

        else:
            raise FileNotFoundError(
                f"Arquivos CSV necessários não encontrados em: {PASTA_DADOS}"
            )

        print("\nImportação concluída com sucesso no PostgreSQL!")
        print(f"Total de instituições importadas: {total_importado}")

    finally:
        conexao.close()


if __name__ == "__main__":
    importar_dados()
