from pydantic import BaseModel, Field
from datetime import date
import hashlib

class SaldoMensal(BaseModel):
    mes: date                  # YYYY-MM-01
    condominio: str
    conta: str
    saldo: float
    documento_id: str | None = None
    origem_raw: str | None = None

    def gerar_hash(self) -> str:
        """Hash único para evitar duplicidade"""
        base = f"{self.mes}-{self.condominio}-{self.conta}"
        return hashlib.sha256(base.encode()).hexdigest()