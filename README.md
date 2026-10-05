# TrocaTroca — Backend (Python / Flask)

API REST em Python para o frontend estático do projeto **TrocaTroca**
(`frontend/js/api.js` já aponta para `http://localhost:5000/api`).

Stack: **Flask + SQLAlchemy (SQLite) + Flask-CORS + PyJWT**.

## Como rodar

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

# (opcional) popula o banco com o usuário de teste e os itens de exemplo
# que já existiam mockados no frontend
python seed.py

python run.py
```

Para rodar os testes:

```bash
python -m unittest discover tests
```

O servidor sobe em `http://localhost:5000`. O banco SQLite é criado
automaticamente em `backend/trocatroca.db` na primeira execução.

Usuário de teste (criado pelo `seed.py`, igual ao que era simulado em
`login.js`): **teste@email.com / 123456**

## Autenticação

Login e cadastro devolvem um token JWT. Envie esse token nas rotas
protegidas via header:

```
Authorization: Bearer <token>
```

## Endpoints

### Usuários / autenticação
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/usuarios` | não | Cadastra usuário `{nome, email, senha}` |
| POST | `/api/login` | não | Login `{email, senha}` → `{token, usuario}` |
| GET | `/api/usuarios/me` | sim | Dados do usuário logado |

### Itens
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/itens?busca=&categoria=` | não | Lista itens disponíveis (filtros opcionais) |
| GET | `/api/itens/meus` | sim | Lista todos os itens do usuário logado |
| GET | `/api/itens/<id>` | não | Detalhe de um item |
| POST | `/api/itens` | sim | Cadastra item `{nome, categoria, estado, descricao, icone?}` |
| PUT | `/api/itens/<id>` | sim (dono) | Edita item |
| DELETE | `/api/itens/<id>` | sim (dono) | Remove item (se disponível) |

### Propostas de troca
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/propostas` | sim | Cria proposta `{item_oferecido_id, item_desejado_id}` |
| GET | `/api/propostas` | sim | Propostas **enviadas** pelo usuário |
| GET | `/api/propostas/recebidas` | sim | Propostas **recebidas** pelo usuário |
| POST | `/api/propostas/<id>/aceitar` | sim (dono do item desejado) | Aceita e conclui a troca |
| POST | `/api/propostas/<id>/recusar` | sim (dono do item desejado) | Recusa a proposta |
| POST | `/api/propostas/<id>/cancelar` | sim (proponente) | Cancela a proposta enviada |

### Histórico e dashboard
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/historico` | sim | Trocas concluídas do usuário |
| GET | `/api/dashboard` | sim | Estatísticas dos cards do dashboard |
| GET | `/api/status` | não | Healthcheck da API |

## Regras de negócio principais

- Categorias válidas: `Livros`, `Eletrônicos`, `Roupas`, `Jogos`, `Outros`.
- Estados válidos: `Novo`, `Excelente`, `Bom`, `Regular`.
- Um item só pode ser oferecido em troca pelo seu próprio dono, e não é
  possível propor troca pelo próprio item.
- Ao **aceitar** uma proposta, os dois itens envolvidos passam para o
  status `Trocado` e um registro de histórico (`Troca`) é criado
  automaticamente. Todas as **outras propostas pendentes** que usam um
  desses itens (oferecido ou desejado) são canceladas automaticamente, e
  a resposta de `/aceitar` inclui `propostas_canceladas` com a quantidade.
  Se um dos itens já não estiver `Disponível` no momento de aceitar, a
  proposta é cancelada e a API responde `409`.
- Senhas nunca são armazenadas em texto puro (hash via Werkzeug).

## Próximo passo no frontend

Hoje `login.js`, `cadastro.js`, `itens.js` e as páginas de propostas usam
dados simulados/hardcoded. Para conectar de verdade a este backend, essas
telas passam a usar `apiRequest(...)` (já definido em `js/api.js`) contra
as rotas acima — por exemplo, `apiRequest("/login", { method: "POST",
body: JSON.stringify({ email, senha }) })` no lugar da simulação atual.
