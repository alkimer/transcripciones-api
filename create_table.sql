CREATE TABLE transcripciones (
    id SERIAL PRIMARY KEY,
    fuente TEXT NOT NULL,
    timestamp_inicio TIMESTAMP NOT NULL,
    timestamp_fin TIMESTAMP NOT NULL,
    texto TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
