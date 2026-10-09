from __future__ import annotations

from sqlalchemy.orm import Session


class JsonRowRepository:
    def __init__(self, db: Session, model, id_attr: str = "id"):
        self.db = db
        self.model = model
        self.id_attr = id_attr

    def get(self, row_id: str):
        return self.db.get(self.model, row_id)

    def list_by_source(self, source_id: str):
        return (
            self.db.query(self.model)
            .filter(self.model.source_id == source_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def add(self, row):
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row):
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
