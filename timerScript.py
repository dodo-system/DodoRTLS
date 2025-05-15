import system
import json

# 1) Configurações gerais do layout
full_cm_w   = 9250.0   # cm (X total: –1850…+7400)
full_cm_h   = 6700.0   # cm (Y total: 0…6700)

region_px_w = 1009.0   # px (largura útil)
region_px_h =  778.0   # px (altura útil)

# Container completo (Perspective) – usado para clamp final
container_px_w  = 1250.0
container_px_h  = 1050.0

# 2) Offset em cm para posicionar A0 no container
offset_cm_x = 1850.0   # cm margem à esquerda
offset_cm_y = 0.0      # cm margem ao topo (A0 em y=0)

# 3) Escalas cm→px
scale_x = region_px_w / full_cm_w
scale_y = region_px_h / full_cm_h

# 4) Converte offset de cm → px
offset_px_x = offset_cm_x * scale_x
offset_px_y = offset_cm_y * scale_y

# 5) Offsets de calibração por antena (cm)
anchor_offsets = {
    0: {"x": 0, "y": 0},
    1: {"x": 0, "y": 0},
    2: {"x": 0, "y": 0},
    3: {"x": 0, "y": 0},
    4: {"x": 0, "y": 0},
    5: {"x": 0, "y": 0},
    6: {"x": 0, "y": 0},
}

# 6) Processa cada tag
for tag_index in [0, 1]:
    url = "http://10.9.83.150:5000/tag/" + str(tag_index)
    try:
        response = system.net.httpGet(url, contentType="application/json")
        data = json.loads(response)
    except Exception as e:
        system.gui.errorBox("Erro HTTP GET tag " + str(tag_index) + ": " + str(e))
        continue

    pos = data.get("position")
    if pos is None:
        system.gui.errorBox("Sem posição para tag " + str(tag_index) + ": " + str(data))
        continue

    # 7) Offset de antena em cm (sem clamp negativo)
    try:
        ranges = data.get("ranges", [])
        if len(ranges) > 0:
            anchor_index = ranges.index(min(ranges))
        else:
            anchor_index = None
    except:
        anchor_index = None
    offs = anchor_offsets.get(anchor_index, {"x":0, "y":0})
    x_cm_corr = pos.get("x", 0) + offs["x"]
    y_cm_corr = pos.get("y", 0) + offs["y"]

    # 8) Converte para px relativo na região útil
    x_rel = x_cm_corr * scale_x
    # inverte eixo Y: y_cm_corr=0 (A0) → y_rel=region_px_h
    y_rel = (full_cm_h - y_cm_corr) * scale_y

    # 9) Soma offset do container
    x_px = offset_px_x + x_rel
    y_px = offset_px_y + y_rel

    # 10) Clamp final dentro dos limites do container inteiro
    if x_px < 0:
        x_px = 0
    if x_px > container_px_w:
        x_px = container_px_w
    if y_px < 0:
        y_px = 0
    if y_px > container_px_h:
        y_px = container_px_h

    # 11) Determina índice de gravação
    tag_id_text = data.get("tag_id", "tag " + str(tag_index))
    parts = tag_id_text.split()
    try:
        write_index = int(parts[-1])
    except:
        write_index = tag_index

    # 12) Gravação nos tags do Ignition
    base = "[default]API/tag_" + str(write_index)
    paths = [base + suf for suf in ["_x","_y","_pixelX","_pixelY"]]
    vals = [x_cm_corr, y_cm_corr, x_px, y_px]

    missing = []
    for p in paths:
        if not system.tag.exists(p):
            missing.append(p)
    if len(missing) > 0:
        system.gui.errorBox("Tags ausentes: " + str(missing))
        continue

    results = system.tag.writeBlocking(paths, vals)
    for idx, status in enumerate(results):
        if str(status) != "Good":
            system.gui.errorBox("Erro escrevendo '" + paths[idx] + "': " + str(status))