from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Proveedor de LLM para el copy: "mistral" | "ollama" ---
    llm_provider: str = "mistral"
    llm_temperature: float = 0.8

    # Mistral API — saca la clave en https://console.mistral.ai
    mistral_api_key: str = ""
    mistral_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-large-latest"

    # Ollama (local) — alternativa sin coste de API
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # --- Generación de imagen: "placeholder" | "comfyui" ---
    # "placeholder" funciona sin GPU (gradientes) para probar el pipeline entero.
    image_provider: str = "placeholder"
    comfyui_url: str = "http://localhost:8188"
    comfyui_workflow: str = "composition/workflows/txt2img.json"

    # --- Tipografía por defecto de la capa de composición ---
    # Fuente con carácter (evita Inter/Roboto). Configurable por marca.
    default_font_url: str = (
        "https://fonts.googleapis.com/css2?"
        "family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,700;12..96,800"
        "&family=Archivo:wght@400;500&display=swap"
    )
    default_display_font: str = "'Bricolage Grotesque', sans-serif"
    default_body_font: str = "'Archivo', sans-serif"

    # --- Rutas ---
    output_dir: str = "outputs"
    db_path: str = "adgen.db"

    # Variables de entorno con prefijo ADGEN_ (p.ej. ADGEN_LLM_MODEL=llama3.1)
    model_config = SettingsConfigDict(env_prefix="ADGEN_")


settings = Settings()
