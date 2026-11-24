"""Lokální E5 nad verzovanými stránkami, atomická aktualizace indexu pgvector."""
import os
from pathlib import Path
import psycopg
from pamet import read, snapshot

MODEL = "Xenova/multilingual-e5-small@761b726dd34fb83930e26aab4e9ac3899aa1fa78:mean-v1"
FILES = Path("/opt/polarita-agent-vault/model")

class Encoder:
    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(FILES/"model_quantized.onnx"),options,providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(FILES/"tokenizer.json"))

    def chunks(self, text):
        offsets = self.tokenizer.encode(text,add_special_tokens=False).offsets
        for begin in range(0,len(offsets),336):
            end = min(begin+384,len(offsets))
            start, stop = offsets[begin][0], offsets[end-1][1]
            yield start, stop
            if end == len(offsets):
                break

    def embedding(self, text):
        import numpy as np
        encoded = self.tokenizer.encode(text)
        if len(encoded.ids)>512:
            raise ValueError("Text dotazu nebo úryvku přesahuje kapacitu modelu.")
        feed = {key: np.asarray([values],dtype="int64") for key,values in
                (("input_ids",encoded.ids),("attention_mask",encoded.attention_mask),("token_type_ids",encoded.type_ids))}
        hidden = self.session.run(["last_hidden_state"],feed)[0][0]
        mask = np.asarray(encoded.attention_mask,dtype=np.bool_)
        vector = hidden[mask].mean(axis=0)
        norm = np.linalg.norm(vector)
        if vector.shape!=(384,) or not np.isfinite(norm) or norm<=0:
            raise ValueError("Model vrátil neplatný vektor.")
        return "["+",".join(format(float(n),".8g") for n in vector/norm)+"]"

def connect(role):
    key = (Path(os.environ["CREDENTIALS_DIRECTORY"])/"postgres").read_text().strip()
    return psycopg.connect(host="/run/polarita-agent-vault-pg",dbname="db_erp_lhutnik",user=role,password=key,
                           options="-c search_path=vault_search,pg_catalog",connect_timeout=10)

def refresh():
    with connect("pol_vault_index") as db:
        db.execute("SELECT pg_advisory_xact_lock(hashtext('polarita-znalostni-index'))")
        commit, pages = snapshot()
        current = db.execute("SELECT revize,model FROM stav WHERE id=1").fetchone()
        if current == (commit,MODEL):
            return commit
        if not current or current[1]!=MODEL:
            db.execute("DELETE FROM stranky")
        existing = dict(db.execute("SELECT cesta,objekt FROM stranky"))
        encoder = None
        for name in sorted(existing.keys()-pages.keys()):
            db.execute("DELETE FROM stranky WHERE cesta=%s",(name,))
        for name,oid in pages.items():
            if existing.get(name)==oid:
                continue
            if encoder is None:
                encoder = Encoder()
            text = read(oid)
            db.execute("DELETE FROM stranky WHERE cesta=%s",(name,))
            db.execute("INSERT INTO stranky (cesta,objekt) VALUES(%s,%s)",(name,oid))
            for i,(start,stop) in enumerate(encoder.chunks(text)):
                vector = encoder.embedding("passage: "+text[start:stop])
                db.execute("INSERT INTO uryvky (cesta,poradi,zacatek,konec,vektor) VALUES(%s,%s,%s,%s,%s::vector)",
                           (name,i,start,stop,vector))
        db.execute("""INSERT INTO stav VALUES(1,%s,%s) ON CONFLICT(id) DO UPDATE
            SET revize=excluded.revize,model=excluded.model""",(commit,MODEL))
        return commit

def search(query, limit):
    if not query.strip() or len(query)>1024 or not 1<=limit<=20:
        raise ValueError("Zadej dotaz do 1024 znaků a počet výsledků od 1 do 20.")
    vector = Encoder().embedding("query: "+query.strip())
    with connect("pol_vault_read") as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        head,pages = snapshot()
        if db.execute("SELECT revize,model FROM stav WHERE id=1").fetchone() != (head,MODEL):
            raise ValueError("Znalostní větev se během hledání změnila. Zopakuj dotaz.")
        result = []
        for name,oid,start,stop,distance in db.execute("""SELECT u.cesta,s.objekt,u.zacatek,u.konec,u.vektor <=> %s::vector AS vzdalenost
                FROM uryvky u JOIN stranky s ON s.cesta=u.cesta ORDER BY u.vektor <=> %s::vector LIMIT %s""",(vector,vector,limit)):
            if pages.get(name)!=oid:
                raise ValueError("Index odkazuje mimo ověřenou revizi.")
            result.append({"cesta":name,"shoda":round(1-distance,5),"uryvek":read(oid)[start:stop]})
        return {"revize":head,"vysledky":result}
