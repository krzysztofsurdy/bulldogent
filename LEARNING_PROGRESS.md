# Learning Progress — Mentor's Notes

Tracking Python learning journey from a senior PHP developer's perspective.

---

## Skills Assessment

### Transferable from PHP (already strong)
- OOP fundamentals, SOLID principles, design patterns
- Dependency injection, abstractions, interfaces
- Testing mindset (TDD, unit/integration split)
- Clean architecture, layered design
- Git workflow, CI/CD concepts
- API design and integration
- Error handling patterns

### Python Concepts — Status

| Concept | Status | Notes |
|---|---|---|
| **Project structure** (`pyproject.toml`, src layout) | Not started | First ticket covers this |
| **Virtual environments** | Familiar | `.venv` already created |
| **Type hints** | Not started | Will feel natural coming from PHP 8 typed properties |
| **f-strings** | Not started | Like PHP `"Hello {$name}"` |
| **`dataclass`** | Not started | Like PHP constructor promotion + auto `__toString` |
| **`Protocol`** | Not started | Like PHP `interface` but structural (duck typing) |
| **Decorators** (`@something`) | Not started | Like PHP attributes but callable — key concept |
| **List/dict comprehensions** | Not started | No PHP equivalent — will feel alien at first |
| **Context managers** (`with`) | Not started | Like try-finally but built into the language |
| **Generators** (`yield`) | Not started | PHP has these too but Python uses them far more |
| **`pytest` fixtures** | Not started | Like PHPUnit `setUp` but composable |
| **Mocking** (`unittest.mock`) | Not started | Like Prophecy/Mockery |
| **`httpx`** | Not started | Like Guzzle |
| **`boto3`** (AWS SDK) | Not started | Like AWS SDK for PHP |
| **Structured logging** (`structlog`) | Not started | Like Monolog JSON formatter |
| **Concurrency** (`ThreadPoolExecutor`) | Not started | No easy PHP parallel — this will be new |
| **Async/await** | Not started | Future milestone |
| **Package publishing** | Not started | Like Packagist but PyPI |

---

## PHP Habits to Watch For

These are patterns that work fine in PHP but aren't idiomatic in Python. I'll flag them during code review.

| PHP Habit | Python Way | Why |
|---|---|---|
| Getters/setters everywhere | Direct attribute access or `@property` | Python trusts the developer; YAGNI applies |
| `private` / `protected` on everything | `_prefix` convention, but often just public | Encapsulation is a convention, not enforced |
| Type-hinting `array` for everything | Use specific types: `list[str]`, `dict[str, int]` | Python has rich built-in types |
| Returning `null` for "not found" | Raise exception or return `None` with `Optional` | Or use sentinel pattern |
| Interfaces for every abstraction | Protocol only when you need polymorphism | Don't over-abstract — YAGNI |
| Long class files with many methods | Smaller modules, top-level functions are fine | Not everything needs a class in Python |
| `AbstractBaseClass` | `Protocol` (structural typing) | ABC requires inheritance; Protocol doesn't |
| `$this->config['key']` | `self.settings.key` (typed attribute) | Pydantic gives you typed access |
| `try {} catch (\Exception $e) {}` | `try: ... except Exception as e:` | Syntax difference, same concept |
| DocBlocks for type info | Type hints inline — docstrings only for "why" | Types are first-class in Python now |

---

## Things to Focus On Next

### Immediate (Milestone 0)
- [ ] Understand `pyproject.toml` structure — read PEP 621
- [ ] Learn the `src/` layout pattern and why it exists
- [ ] Get comfortable with `ruff` and `mypy` output — run them constantly
- [ ] Write your first `pytest` test — notice how different it feels from PHPUnit

### Soon (Milestone 1–2)
- [ ] Decorators — understand them deeply, they're everywhere in Python
- [ ] `dataclass` — use it for every DTO, get it into muscle memory
- [ ] `Protocol` — write one, see how structural typing "just works"
- [ ] f-strings and string manipulation — different from PHP's approach

### Later (Milestone 3+)
- [ ] List comprehensions — practice writing them, they replace many loops
- [ ] Context managers — `with` statements for resource management
- [ ] Generators — `yield` for lazy data processing
- [ ] `ThreadPoolExecutor` — your first taste of real Python concurrency

---

## Review Log

Notes from code reviews, common mistakes, and breakthroughs.

### Session 1 — 2025-02-21
- Project planning session only, no code written yet
- Developer has clear understanding of architecture goals
- Strong foundation in patterns — the challenge will be translating them to Pythonic idioms
- ML/DL goal noted — steering toward habits that transfer (type hints, data structures, generators)

---

## Recommended Reading Queue

Add to this as topics come up:

1. **Now:** [Python Packaging User Guide](https://packaging.python.org/) — understand `pyproject.toml`
2. **Now:** [Real Python — Python Project Structure](https://realpython.com/python-application-layouts/)
3. **Soon:** [Python Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)
4. **Soon:** [Pytest Getting Started](https://docs.pytest.org/en/stable/getting-started.html)
5. **Later:** [Python Decorators Primer](https://realpython.com/primer-on-python-decorators/)
6. **Later:** [Fluent Python (book)](https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/) — the "PHP Objects, Patterns, and Practice" equivalent for Python
