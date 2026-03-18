import re
import json
import time
from github import Github, Auth
from jinja2 import Environment, FileSystemLoader
import os
import random
from dotenv import load_dotenv
import sys  # para usar argumentos... python index2.py --watch

# load_dotenv()
try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

CACHE_FILE = "data.json"

REFRESH = "--watch" in sys.argv

FEATURED_TAGS = {
    "hackathon",
    "project",
    "2025",
}  # buscara solo repositorios que tengan alguno de estos tags

IGNORE_IMAGE_WORDS = [
    "badge",
    "shield",
    "travis",
    "coveralls",
    "img.shields",
]


COLOR_PALETTE = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#F7B801",
    "#9B5DE5",
    "#00BBF9",
    "#F15BB5",
    "#00F5D4",
]

####################################


def get_random_color():
    return random.choice(COLOR_PALETTE)


# sera consistente entre builds
def get_repo_color(repo_name):
    index = abs(hash(repo_name)) % len(COLOR_PALETTE)
    return COLOR_PALETTE[index]


####################################


def valid_image(url):
    if not url:
        return False
    return not any(word in url.lower() for word in IGNORE_IMAGE_WORDS)


def convert_relative_to_raw(repo, url):
    if url.startswith("http"):
        return url

    base = f"https://raw.githubusercontent.com/{repo.owner.login}/{repo.name}/{repo.default_branch}/"
    return base + url.lstrip("./")


def extract_readme_image(repo, readme_text):
    matches = re.findall(r"!\[.*?\]\((.*?)\)", readme_text)

    for img in matches:
        img = convert_relative_to_raw(repo, img)

        if valid_image(img):
            return img

    return None


def get_local_image(repo):
    path = f"images/{repo.name}.png"
    if os.path.exists(path):
        return "/" + path
    return None


def get_opengraph_image(repo):
    return f"https://opengraph.githubassets.com/1/{repo.owner.login}/{repo.name}"


# si encuentra imagen en readme, usa esa, si no hay usa local, si no hay, ... ahora usa blank.png
def get_best_image(repo, readme_text):
    readme_image = extract_readme_image(repo, readme_text)

    if readme_image:
        return readme_image

    local = get_local_image(repo)

    if local:
        return local

    # private repos dont seem to have a opengraph image
    # open_g = get_opengraph_image(repo)
    # if open_g:
    #     return get_opengraph_image(repo)

    return "/images/blank.png"


####################################


def get_readme(repo):
    """obtiene el contenido  del  readme,en caso no haya nadadevuelve string vacio"""
    try:
        repo_content = repo.get_readme()
        readme_text = repo_content.decoded_content.decode("utf-8")
    except Exception:
        readme_text = ""
    return readme_text


def extract_first_blockquote(text):
    match = re.search(r"(?m)^> (.+)", text)
    return match.group(1).strip() if match else None


####################################


def get_github_data(token, username):
    auth = Auth.Token(token)
    g = Github(auth=auth, per_page=100)
    user = g.get_user(username)

    # Obtener todos los repos públicos y privados
    # repos = user.get_repos(visibility="all", sort="updated") no
    # repos = user.get_repos(type="owner", sort="updated") no
    repos = user.get_repos()
    repos_list = list(repos)
    total_repos = len(repos_list)

    remaining = g.get_rate_limit().resources.core.remaining
    print("queda", remaining)
    if remaining < 50:
        print("queda menos de 50")
        time.sleep(60)

    data = {
        "name": user.name or user.login,
        "bio": user.bio or "",
        "avatar": user.avatar_url,
        "followers": user.followers,
        "following": user.following,
        "repos": [],
    }

    print(f"📦 Total repos encontrados: {total_repos}")
    print("───────────────────────────────────────")

    total_processed = 0
    matched = 0

    # debug
    # for repo in g.get_user().get_repos():
    # print(repo.name, repo.private)

    for index, repo in enumerate(repos_list, start=1):
        total_processed += 1

        # Omitir forks y archivados
        if repo.fork or repo.archived:
            continue

        # Obtener topics (PyGithub los incluye automáticamente)
        topics = [t.lower() for t in (repo.topics or [])]

        # debug
        # print(f"[{index}/{total_repos}] {repo.name} → topics: {topics}")

        # Filtrar por tags
        if FEATURED_TAGS.intersection(topics):
            matched += 1

            readme_text = get_readme(repo)

            image_url = get_best_image(repo, readme_text)

            lang_list = list((repo.get_languages() or {}).keys())

            # default_image_url = repo.name + ".png"

            data["repos"].append(
                {
                    "name": repo.name,
                    "url": repo.html_url,
                    "description": repo.description or "No description",
                    "stars": repo.stargazers_count,
                    "languages": lang_list,
                    "topics": topics,
                    "updated_at": repo.updated_at.isoformat(),
                    "private": repo.private,
                    "image_url": image_url,
                    "readme": readme_text,
                    "blockquote": extract_first_blockquote(readme_text),
                    "color": get_random_color(),
                }
            )

    # Ordenar por estrellas y fecha
    data["repos"].sort(key=lambda r: (r["stars"], r["updated_at"]), reverse=True)

    print("───────────────────────────────────────")
    print(f"✅ Total procesados: {total_processed}")
    print(f"⭐ Repos destacados encontrados: {matched}")

    return data


def generate_html(data):
    # env = Environment(loader=FileSystemLoader("templates"))
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")))

    template = env.get_template("index.html")

    html_output = template.render(user=data)
    # os.makedirs("dist", exist_ok=True)

    # with open("dist/index.html", "w", encoding="utf-8") as f:
    #     f.write(html_output)
    # para gh pages b
    output_path = "index.html"  # directo en root
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)

    print("HTML done")


def generate_json(data):
    """
    https://www.geeksforgeeks.org/python/create-a-file-if-not-exists-in-python/

    si elarchivo no existe,lo crea
    copia data enelarchivo
        :param data: Description
    """

    with open(CACHE_FILE, "w") as w:
        json.dump(data, w)


def read_json():
    file_path = "sample.json"
    if os.path.exists(file_path):
        with open("sample.json", "r") as f:
            data = json.load(f)
    else:
        print("no existe")


if __name__ == "__main__":
    token = os.getenv("GH_TOKEN")
    username = os.getenv("GH_USERNAME")

    # si no coloco --watch y el data.json existe, usa eso
    if os.path.exists(CACHE_FILE) and not REFRESH:
        print("usando cache local")
        with open(CACHE_FILE) as f:
            data = json.load(f)
        generate_html(data)
    # de lo contrario, intentara usar las variables del env y obtener datos de github api
    elif not token or not username:
        print("Faltan variables GH_TOKEN o GH_USERNAME en .env")
    else:
        print("obteniendo datos de gh")
        data = get_github_data(token, username)
        generate_html(data)
        generate_json(data)
