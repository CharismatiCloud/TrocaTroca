import unittest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Item, Usuario


class ConfigTeste(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class PropostasConflitantesTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(ConfigTeste)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.ana = self._criar_usuario("Ana", "ana@email.com")
        self.bia = self._criar_usuario("Bia", "bia@email.com")
        self.caio = self._criar_usuario("Caio", "caio@email.com")

        self.item_ana = self._criar_item("Livro da Ana", self.ana)
        self.item_bia = self._criar_item("Jogo da Bia", self.bia)
        self.item_caio = self._criar_item("Fone do Caio", self.caio)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _criar_usuario(self, nome, email):
        u = Usuario(nome=nome, email=email)
        u.set_senha("123456")
        db.session.add(u)
        db.session.commit()
        return u

    def _criar_item(self, nome, dono):
        i = Item(nome=nome, categoria="Outros", estado="Bom",
                 descricao="", proprietario_id=dono.id)
        db.session.add(i)
        db.session.commit()
        return i

    def _login(self, email):
        r = self.client.post("/api/login", json={"email": email, "senha": "123456"})
        return {"Authorization": f"Bearer {r.get_json()['token']}"}

    def _propor(self, email, oferecido, desejado):
        r = self.client.post(
            "/api/propostas",
            json={"item_oferecido_id": oferecido.id, "item_desejado_id": desejado.id},
            headers=self._login(email),
        )
        self.assertEqual(r.status_code, 201)
        return r.get_json()["id"]

    def test_aceitar_cancela_outras_propostas_pendentes_do_mesmo_item(self):
        # Ana e Caio disputam o item da Bia
        p_ana = self._propor("ana@email.com", self.item_ana, self.item_bia)
        p_caio = self._propor("caio@email.com", self.item_caio, self.item_bia)

        r = self.client.post(f"/api/propostas/{p_ana}/aceitar",
                             headers=self._login("bia@email.com"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["propostas_canceladas"], 1)

        r = self.client.get("/api/propostas", headers=self._login("caio@email.com"))
        status = {p["id"]: p["status"] for p in r.get_json()}
        self.assertEqual(status[p_caio], "cancelada")

    def test_nao_e_possivel_aceitar_proposta_cancelada(self):
        p_ana = self._propor("ana@email.com", self.item_ana, self.item_bia)
        p_caio = self._propor("caio@email.com", self.item_caio, self.item_bia)
        self.client.post(f"/api/propostas/{p_ana}/aceitar",
                         headers=self._login("bia@email.com"))

        r = self.client.post(f"/api/propostas/{p_caio}/aceitar",
                             headers=self._login("bia@email.com"))
        self.assertEqual(r.status_code, 400)

    def test_aceitar_sem_conflitos_retorna_zero_canceladas(self):
        p_ana = self._propor("ana@email.com", self.item_ana, self.item_bia)
        r = self.client.post(f"/api/propostas/{p_ana}/aceitar",
                             headers=self._login("bia@email.com"))
        self.assertEqual(r.get_json()["propostas_canceladas"], 0)


if __name__ == "__main__":
    unittest.main()
