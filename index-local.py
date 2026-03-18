from index import get_github_data, generate_html

data = get_github_data("tu_token", "tu_usuario")
generate_html(data)
