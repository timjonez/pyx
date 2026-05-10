from typing import List


def greeting(name: str) -> str:
    return (
        <div class="greeting">
            <h1>Hello, {name}!</h1>
            <p>Welcome to pyx.</p>
        </div>
    )


def todo_list(items: List[str]) -> str:
    return (
        <ul class="todo-list">
            for item in items:
                <li>{item}</li>
        </ul>
    )


def conditional(user) -> str:
    return (
        <div>
            if user:
                <p>Logged in as {user}</p>
            else:
                <p>Please log in</p>
        </div>
    )


def mixed_content(data: dict) -> str:
    return (
        greeting('World')
        <article>
            <header>
                <h2>{data["title"]}</h2>
            </header>
            <section>
                for para in data["paragraphs"]:
                    <p>{para}</p>
            </section>
            <footer>
                <p>{f"Created on {data['date']}"}</p>
            </footer>
        </article>
    )
