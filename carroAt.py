import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import math

# ── Estado global ─────────────────────────────────────────────────────────────
angulo_y  = 0.0
pos_z     = 0.0
rot_roda  = 0.0

VEL_MOV   = 0.4
VEL_GIRO  = 3.0
RAIO_RODA = 5.42


# ── Decodifica cor do nome do material  wire_RRRGGGBBB ───────────────────────
def mat_to_color(mat_name):
    """Converte 'wire_RRRGGGBBB' em (r, g, b) normalizados 0-1."""
    try:
        digits = mat_name.replace('wire_', '')
        r = int(digits[0:3]) / 255.0
        g = int(digits[3:6]) / 255.0
        b = int(digits[6:9]) / 255.0
        return (r, g, b)
    except Exception:
        return (0.7, 0.7, 0.7)


# ── Carregamento do OBJ com materiais ────────────────────────────────────────
def load_obj(path):
    """
    Retorna:
        vertices : list of (x,y,z)
        groups   : dict { nome_grupo : [ (material_str, [faces]) ] }
    """
    vertices  = []
    groups    = {}
    cur_group = 'default'
    cur_mat   = 'wire_128128128'
    cur_faces = []
    pending   = []

    with open(path, 'r') as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('v '):
                p = line.split()
                vertices.append((float(p[1]), float(p[2]), float(p[3])))

            elif line.startswith('g ') or line.startswith('o '):
                if cur_faces:
                    pending.append((cur_mat, cur_faces))
                    cur_faces = []
                if pending:
                    groups.setdefault(cur_group, []).extend(pending)
                    pending = []
                cur_group = line[2:].strip()

            elif line.startswith('usemtl '):
                if cur_faces:
                    pending.append((cur_mat, cur_faces))
                    cur_faces = []
                cur_mat = line[7:].strip()

            elif line.startswith('f '):
                parts = line.split()[1:]
                face  = [int(p.split('/')[0]) - 1 for p in parts]
                cur_faces.append(face)

    if cur_faces:
        pending.append((cur_mat, cur_faces))
    if pending:
        groups.setdefault(cur_group, []).extend(pending)

    return vertices, groups


# ── Display list colorida (um segmento por material) ─────────────────────────
def build_dl_colored(vertices, segments):
    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)
    for mat, faces in segments:
        r, g, b = mat_to_color(mat)
        glColor3f(r, g, b)
        glBegin(GL_TRIANGLES)
        for face in faces:
            for i in range(1, len(face) - 1):
                glVertex3fv(vertices[face[0]])
                glVertex3fv(vertices[face[i]])
                glVertex3fv(vertices[face[i + 1]])
        glEnd()
    glEndList()
    return dl


# ── OpenGL setup ──────────────────────────────────────────────────────────────
def init():
    glClearColor(0.15, 0.15, 0.18, 1.0)
    glEnable(GL_DEPTH_TEST)
    glShadeModel(GL_SMOOTH)


def resize(window, w, h):
    if h == 0:
        h = 1
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, w / h, 0.1, 500.0)
    glMatrixMode(GL_MODELVIEW)


# ── Eixos ─────────────────────────────────────────────────────────────────────
def draw_axes(size=20):
    glLineWidth(2.0)
    glBegin(GL_LINES)
    glColor3f(1, 0, 0); glVertex3f(0,0,0); glVertex3f(size,0,0)
    glColor3f(0, 1, 0); glVertex3f(0,0,0); glVertex3f(0,size,0)
    glColor3f(0, 0, 1); glVertex3f(0,0,0); glVertex3f(0,0,size)
    glEnd()
    glLineWidth(1.0)


# ── Chão ──────────────────────────────────────────────────────────────────────
grass_tex = None

def load_texture(path):
    try:
        from PIL import Image
        import numpy as np
        img  = Image.open(path).convert('RGB').transpose(Image.FLIP_TOP_BOTTOM)
        data = np.array(img, dtype=np.uint8)
        tid  = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB,
                     img.width, img.height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, data)
        print("  Textura de grama carregada!")
        return tid
    except Exception as e:
        print(f"  Aviso: textura não carregada ({e}) — usando cor sólida.")
        return None


def draw_floor():
    SIZE = 200
    TILE = 20
    if grass_tex:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, grass_tex)
        glColor3f(1, 1, 1)
    else:
        glColor3f(0.25, 0.55, 0.25)

    glBegin(GL_QUADS)
    glTexCoord2f(0,    0);    glVertex3f(-SIZE, 0, -SIZE)
    glTexCoord2f(TILE, 0);    glVertex3f( SIZE, 0, -SIZE)
    glTexCoord2f(TILE, TILE); glVertex3f( SIZE, 0,  SIZE)
    glTexCoord2f(0,    TILE); glVertex3f(-SIZE, 0,  SIZE)
    glEnd()

    if grass_tex:
        glDisable(GL_TEXTURE_2D)


# ── Display principal ─────────────────────────────────────────────────────────
def display(dl_frame, dl_front, dl_rear,
            fx, fy, fz, rx, ry, rz):
    global angulo_y, pos_z, rot_roda

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    gluLookAt(30, 40, 80,  0, 10, 0,  0, 1, 0)

    draw_floor()
    draw_axes(30)

    glPushMatrix()
    glRotatef(angulo_y, 0, 1, 0)
    glTranslatef(0, 0, pos_z)

    glCallList(dl_frame)

    glPushMatrix()
    glTranslatef(fx, fy, fz)
    glRotatef(rot_roda, 1, 0, 0)
    glTranslatef(-fx, -fy, -fz)
    glCallList(dl_front)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(rx, ry, rz)
    glRotatef(rot_roda, 1, 0, 0)
    glTranslatef(-rx, -ry, -rz)
    glCallList(dl_rear)
    glPopMatrix()

    glPopMatrix()


# ── Teclado ───────────────────────────────────────────────────────────────────
def key_callback(window, key, scancode, action, mods):
    global angulo_y, pos_z, rot_roda
    if action not in (glfw.PRESS, glfw.REPEAT):
        return
    if key in (glfw.KEY_LEFT,  glfw.KEY_A):
        angulo_y -= VEL_GIRO
    elif key in (glfw.KEY_RIGHT, glfw.KEY_D):
        angulo_y += VEL_GIRO
    elif key in (glfw.KEY_UP,   glfw.KEY_W):
        pos_z    -= VEL_MOV
        rot_roda -= (VEL_MOV / RAIO_RODA) * (180 / math.pi)
    elif key in (glfw.KEY_DOWN,  glfw.KEY_S):
        pos_z    += VEL_MOV
        rot_roda += (VEL_MOV / RAIO_RODA) * (180 / math.pi)
    elif key == glfw.KEY_ESCAPE:
        glfw.set_window_should_close(window, True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global grass_tex

    print("Carregando bicycle.obj…")
    vertices, groups = load_obj("bicycle.obj")
    print(f"  {len(vertices)} vértices, {len(groups)} grupos.")

    FRONT_WHEEL = {"Cylinder005"}
    REAR_WHEEL  = {"Cylinder010"}

    front_segs, rear_segs, frame_segs = [], [], []
    for name, segs in groups.items():
        if name in FRONT_WHEEL:
            front_segs.extend(segs)
        elif name in REAR_WHEEL:
            rear_segs.extend(segs)
        else:
            frame_segs.extend(segs)

    def group_center(segs):
        xs = [vertices[i][0] for _, faces in segs for f in faces for i in f]
        ys = [vertices[i][1] for _, faces in segs for f in faces for i in f]
        zs = [vertices[i][2] for _, faces in segs for f in faces for i in f]
        return ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2)

    fx, fy, fz = group_center(front_segs)
    rx, ry, rz = group_center(rear_segs)

    if not glfw.init():
        return
    window = glfw.create_window(1280, 720,
        "Bicicleta 3D  |  W/S = frente/trás   A/D = esq/dir   ESC = sair",
        None, None)
    if not window:
        glfw.terminate()
        return

    glfw.make_context_current(window)
    glfw.set_window_size_callback(window, resize)
    glfw.set_key_callback(window, key_callback)
    init()

    grass_tex = load_texture("grass_grass_0118_02_preview.jpg")

    print("Compilando display lists com cores do MTL…")
    dl_frame = build_dl_colored(vertices, frame_segs)
    dl_front = build_dl_colored(vertices, front_segs)
    dl_rear  = build_dl_colored(vertices, rear_segs)
    print("Pronto!")

    while not glfw.window_should_close(window):
        display(dl_frame, dl_front, dl_rear, fx, fy, fz, rx, ry, rz)
        glfw.swap_buffers(window)
        glfw.poll_events()

    glDeleteLists(dl_frame, 1)
    glDeleteLists(dl_front,  1)
    glDeleteLists(dl_rear,   1)
    glfw.terminate()


if __name__ == "__main__":
    main()