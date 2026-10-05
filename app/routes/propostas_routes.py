from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.auth import login_obrigatorio
from app.extensions import db
from app.models import Item, Proposta, Troca

propostas_bp = Blueprint("propostas", __name__)


@propostas_bp.post("/propostas")
@login_obrigatorio
def criar_proposta():
    """Cria uma proposta de troca (botão 'Propor troca' em detalhe-item.html)."""
    dados = request.get_json(silent=True) or {}

    item_oferecido_id = dados.get("item_oferecido_id")
    item_desejado_id = dados.get("item_desejado_id")

    if not item_oferecido_id or not item_desejado_id:
        return jsonify({"erro": "Informe o item oferecido e o item desejado."}), 400

    item_oferecido = Item.query.get(item_oferecido_id)
    item_desejado = Item.query.get(item_desejado_id)

    if not item_oferecido or not item_desejado:
        return jsonify({"erro": "Item oferecido ou item desejado não encontrado."}), 404

    if item_oferecido.proprietario_id != request.usuario_atual.id:
        return jsonify({"erro": "Você só pode oferecer itens que são seus."}), 403

    if item_desejado.proprietario_id == request.usuario_atual.id:
        return jsonify({"erro": "Você não pode propor troca por um item seu."}), 400

    if item_oferecido.status != "Disponível" or item_desejado.status != "Disponível":
        return jsonify({"erro": "Ambos os itens precisam estar disponíveis."}), 400

    proposta = Proposta(
        proponente_id=request.usuario_atual.id,
        item_oferecido_id=item_oferecido.id,
        item_desejado_id=item_desejado.id,
        status="pendente",
    )

    db.session.add(proposta)
    db.session.commit()

    return jsonify(proposta.to_dict()), 201


@propostas_bp.get("/propostas")
@login_obrigatorio
def listar_propostas_enviadas():
    """Propostas enviadas pelo usuário autenticado (tela propostas.html)."""
    propostas = (
        Proposta.query.filter_by(proponente_id=request.usuario_atual.id)
        .order_by(Proposta.criado_em.desc())
        .all()
    )
    return jsonify([p.to_dict() for p in propostas]), 200


@propostas_bp.get("/propostas/recebidas")
@login_obrigatorio
def listar_propostas_recebidas():
    """Propostas recebidas pelo usuário autenticado (tela recebidas.html).

    São as propostas feitas por outras pessoas para itens que pertencem
    ao usuário autenticado.
    """
    propostas = (
        Proposta.query.join(Item, Proposta.item_desejado_id == Item.id)
        .filter(Item.proprietario_id == request.usuario_atual.id)
        .order_by(Proposta.criado_em.desc())
        .all()
    )
    return jsonify([p.to_dict() for p in propostas]), 200


def _buscar_proposta_pendente(proposta_id):
    proposta = Proposta.query.get(proposta_id)
    if not proposta:
        return None, (jsonify({"erro": "Proposta não encontrada."}), 404)
    if proposta.status != "pendente":
        return None, (jsonify({"erro": "Esta proposta já foi respondida."}), 400)
    return proposta, None


def _encerrar_propostas_conflitantes(proposta_aceita):
    """Cancela as outras propostas pendentes que usam algum dos itens trocados.

    Depois que uma troca é concluída, os dois itens ficam com status
    'Trocado' e não podem mais participar de outra negociação. Qualquer
    proposta pendente que ainda os referencie (como item oferecido ou
    desejado) passa a 'cancelada'.

    Retorna a quantidade de propostas encerradas.
    """
    ids_itens = [proposta_aceita.item_oferecido_id, proposta_aceita.item_desejado_id]

    conflitantes = Proposta.query.filter(
        Proposta.id != proposta_aceita.id,
        Proposta.status == "pendente",
        or_(
            Proposta.item_oferecido_id.in_(ids_itens),
            Proposta.item_desejado_id.in_(ids_itens),
        ),
    ).all()

    for outra in conflitantes:
        outra.status = "cancelada"

    return len(conflitantes)


@propostas_bp.post("/propostas/<int:proposta_id>/cancelar")
@login_obrigatorio
def cancelar_proposta(proposta_id):
    """Cancela uma proposta enviada. Só o próprio proponente pode cancelar."""
    proposta, erro = _buscar_proposta_pendente(proposta_id)
    if erro:
        return erro

    if proposta.proponente_id != request.usuario_atual.id:
        return jsonify({"erro": "Você não pode cancelar essa proposta."}), 403

    proposta.status = "cancelada"
    db.session.commit()

    return jsonify(proposta.to_dict()), 200


@propostas_bp.post("/propostas/<int:proposta_id>/aceitar")
@login_obrigatorio
def aceitar_proposta(proposta_id):
    """Aceita uma proposta recebida. Só o dono do item desejado pode aceitar.

    Ao aceitar, os dois itens envolvidos passam para o status 'Trocado'
    e um registro de histórico (Troca) é criado.
    """
    proposta, erro = _buscar_proposta_pendente(proposta_id)
    if erro:
        return erro

    if proposta.item_desejado.proprietario_id != request.usuario_atual.id:
        return jsonify({"erro": "Você não pode aceitar essa proposta."}), 403

    # Garante que nenhum dos itens foi trocado por outra proposta enquanto
    # esta ainda estava pendente.
    if (
        proposta.item_oferecido.status != "Disponível"
        or proposta.item_desejado.status != "Disponível"
    ):
        proposta.status = "cancelada"
        db.session.commit()
        return jsonify({"erro": "Um dos itens não está mais disponível para troca."}), 409

    proposta.status = "aceita"
    proposta.item_oferecido.status = "Trocado"
    proposta.item_desejado.status = "Trocado"
    canceladas = _encerrar_propostas_conflitantes(proposta)

    troca = Troca(
        proposta_id=proposta.id,
        usuario1_id=proposta.proponente_id,
        usuario2_id=proposta.item_desejado.proprietario_id,
        item1_id=proposta.item_oferecido_id,
        item2_id=proposta.item_desejado_id,
    )
    db.session.add(troca)
    db.session.commit()

    resposta = proposta.to_dict()
    resposta["propostas_canceladas"] = canceladas
    return jsonify(resposta), 200


@propostas_bp.post("/propostas/<int:proposta_id>/recusar")
@login_obrigatorio
def recusar_proposta(proposta_id):
    """Recusa uma proposta recebida. Só o dono do item desejado pode recusar."""
    proposta, erro = _buscar_proposta_pendente(proposta_id)
    if erro:
        return erro

    if proposta.item_desejado.proprietario_id != request.usuario_atual.id:
        return jsonify({"erro": "Você não pode recusar essa proposta."}), 403

    proposta.status = "recusada"
    db.session.commit()

    return jsonify(proposta.to_dict()), 200
