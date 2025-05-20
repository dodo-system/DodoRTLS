from flask import Flask, request, jsonify
import numpy as np
import time
from scipy.optimize import least_squares

app = Flask(__name__)

# ------------------------------------------------------------------------------
# Configuração das posições conhecidas das âncoras (IDs 0 a 7).
# As posições (x, y) estão definidas em centímetros. Todas as âncoras estão instaladas a 113 cm do chão.
anchor_positions = {
    0: (0.0, 0.0),
    1: (0.0, 3594.0),
    2: (0.0, 7032.0),
    3: (3500.0, 0.0),
    4: (3500.0, 3550.0),
    5: (3500.0, 6600.0),
    6: (5600.0, 3700.0)
}
default_anchor_height = 113  # altura das âncoras em cm

# ------------------------------------------------------------------------------
# Estrutura para armazenar os dados enviados por cada âncora.
# Cada chave é o anchor_id (0 a 7) e o valor é um dicionário,
# onde cada chave é o identificador da tag (ex.: "tag 0")
# e o valor é um dicionário contendo "distancia", "rssi" e "timestamp".
anchors_data = {}

# Tempo (em segundos) para expirar medições antigas.
DATA_EXPIRY = 30  # por exemplo, 30 segundos

# ------------------------------------------------------------------------------
# Função para limpar medições antigas.
def clean_old_measurements():
    current_time = time.time()
    for anchor_id in list(anchors_data.keys()):
        for tag in list(anchors_data[anchor_id].keys()):
            timestamp = anchors_data[anchor_id][tag].get("timestamp", 0)
            if current_time - timestamp > DATA_EXPIRY:
                del anchors_data[anchor_id][tag]
        if not anchors_data[anchor_id]:
            del anchors_data[anchor_id]

# ------------------------------------------------------------------------------
# Endpoint para receber os dados via POST.
# Payload esperado:
# {
#   "anchor_id": <número inteiro de 0 a 7>,
#   "tags": {
#       "tag 0": { "distancia": <valor>, "rssi": <valor> },
#       "tag 1": { "distancia": <valor>, "rssi": <valor> },
#       ...
#   }
# }
@app.route('/endpoint', methods=['POST'])
def receive_data():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "JSON inválido ou não informado."}), 400

    if "anchor_id" not in data or "tags" not in data:
        return jsonify({"error": "Os campos 'anchor_id' e 'tags' são obrigatórios."}), 400

    anchor_id = data["anchor_id"]
    tags = data["tags"]

    if not isinstance(anchor_id, int) or anchor_id < 0 or anchor_id > 7:
        return jsonify({"error": "anchor_id deve ser um número inteiro entre 0 e 7."}), 400

    if not isinstance(tags, dict):
        return jsonify({"error": "'tags' deve ser um objeto/dict."}), 400

    # Cria o dicionário para esse anchor, se não existir.
    if anchor_id not in anchors_data:
        anchors_data[anchor_id] = {}

    current_time = time.time()
    for tag, measurement in tags.items():
        if not isinstance(measurement, dict):
            continue
        if "distancia" not in measurement or "rssi" not in measurement:
            continue
        try:
            distancia = float(measurement["distancia"])
            rssi = float(measurement["rssi"])
        except ValueError:
            continue

        # Registra a medição com o timestamp atual.
        anchors_data[anchor_id][tag] = {
            "distancia": distancia,
            "rssi": rssi,
            "timestamp": current_time
        }

    return jsonify({
        "status": "sucesso",
        "anchor_id": anchor_id,
        "tags_recebidas": len(tags)
    })

# ------------------------------------------------------------------------------
# Função de trilateração 3D utilizando otimização não-linear.
# Aqui minimizamos a soma dos quadrados das diferenças entre as distâncias medidas
# e as distâncias calculadas considerando (x, y, z) e a altura das âncoras.
def trilaterate_nonlinear_3D(points, distances, anchor_heights):
    def residuals(vars, points, distances, anchor_heights):
        x, y, z = vars
        res = []
        for i, ((xi, yi), d) in enumerate(zip(points, distances)):
            res.append(np.sqrt((x - xi)**2 + (y - yi)**2 + (z - anchor_heights[i])**2) - d)
        return res

    # Chute inicial: média dos x e y dos pontos, e para z, usamos a altura das âncoras (ex.: 113 cm)
    initial_guess = [np.mean([p[0] for p in points]), np.mean([p[1] for p in points]), anchor_heights[0]]
    result = least_squares(residuals, initial_guess, args=(points, distances, anchor_heights))
    return result.x  # Retorna [x, y, z]

# ------------------------------------------------------------------------------
# Função para aplicar clamp (definir como 0 se o valor for negativo muito pequeno)
# e arredondar para 2 casas decimais.
def clamp_and_round(value, threshold=0.5):
    if value < 0 and abs(value) < threshold:
        return 0.0
    return round(value, 2)

# ------------------------------------------------------------------------------
# Endpoint para calcular a posição (x, y, z) de uma tag via trilateração 3D.
@app.route('/tag/<tag_id>', methods=['GET'])
def get_tag_position(tag_id):
    clean_old_measurements()
    tag_key = "tag " + str(tag_id)
    points = []       # coordenadas (x, y) das âncoras
    distances = []    # distâncias medidas (em cm)
    heights = []      # altura de cada âncora (em cm), todas serão default_anchor_height

    for anchor_id, tag_measurements in anchors_data.items():
        if tag_key in tag_measurements and anchor_id in anchor_positions:
            ponto = anchor_positions[anchor_id]  # (x, y)
            distancia_cm = tag_measurements[tag_key]["distancia"]
            points.append(ponto)
            distances.append(distancia_cm)
            heights.append(default_anchor_height)

    if len(points) < 3:
        return jsonify({
            "error": f"Medições insuficientes para trilateração. São necessárias pelo menos 3 âncoras para a tag '{tag_key}'."
        }), 400
    try:
        result = trilaterate_nonlinear_3D(points, distances, heights)
        x, y, z = result
        x = clamp_and_round(x)
        y = clamp_and_round(y)
        z = clamp_and_round(z)
    except Exception as e:
        return jsonify({"error": f"Erro na trilateração: {str(e)}"}), 500

    return jsonify({
        "tag_id": tag_key,
        "position": {"x": x, "y": y, "z": z},
        "anchors_usadas": len(points)
    })

# ------------------------------------------------------------------------------
# Endpoint para visualizar todos os dados acumulados (para depuração).
@app.route('/anchors', methods=['GET'])
def get_all_anchors():
    clean_old_measurements()
    return jsonify(anchors_data)

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
