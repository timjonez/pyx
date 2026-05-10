"""Example showing naked function calls inside JSX blocks."""


def greeting(name: str) -> str:
    return (
        <div class="greeting">
            <h1>Hello, {name}!</h1>
            <p>Welcome to pyx.</p>
        </div>
    )


def mixed_content(data: dict) -> str:
    return (
        <div>
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
        </div>
    )
