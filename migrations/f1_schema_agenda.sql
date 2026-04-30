-- ============================================================================
-- ETAPA F.1 · Schema Supabase para Calendario de Uso da Academia
-- ============================================================================
-- Cria 4 tabelas novas: profissionais, ambientes, agenda_regras, horario_funcionamento
-- Todas com RLS estrito (acesso so do admin_uid)
-- Popula dados iniciais: 3 profissionais + 2 ambientes
-- IDEMPOTENTE: pode rodar 2x sem quebrar
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. TABELA: profissionais
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profissionais (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('treino', 'calistenia', 'kids', 'outro')),
    cor_hex TEXT NOT NULL CHECK (cor_hex ~ '^#[0-9A-Fa-f]{6}$'),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.profissionais ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin_select_profissionais" ON public.profissionais;
DROP POLICY IF EXISTS "admin_insert_profissionais" ON public.profissionais;
DROP POLICY IF EXISTS "admin_update_profissionais" ON public.profissionais;
DROP POLICY IF EXISTS "admin_delete_profissionais" ON public.profissionais;

CREATE POLICY "admin_select_profissionais"
    ON public.profissionais FOR SELECT
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_insert_profissionais"
    ON public.profissionais FOR INSERT
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_update_profissionais"
    ON public.profissionais FOR UPDATE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid)
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_delete_profissionais"
    ON public.profissionais FOR DELETE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);


-- ---------------------------------------------------------------------------
-- 2. TABELA: ambientes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ambientes (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    area_m2 NUMERIC(8, 2) NOT NULL CHECK (area_m2 > 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.ambientes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin_select_ambientes" ON public.ambientes;
DROP POLICY IF EXISTS "admin_insert_ambientes" ON public.ambientes;
DROP POLICY IF EXISTS "admin_update_ambientes" ON public.ambientes;
DROP POLICY IF EXISTS "admin_delete_ambientes" ON public.ambientes;

CREATE POLICY "admin_select_ambientes"
    ON public.ambientes FOR SELECT
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_insert_ambientes"
    ON public.ambientes FOR INSERT
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_update_ambientes"
    ON public.ambientes FOR UPDATE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid)
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_delete_ambientes"
    ON public.ambientes FOR DELETE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);


-- ---------------------------------------------------------------------------
-- 3. TABELA: agenda_regras
-- ---------------------------------------------------------------------------
-- Convencao de dia_semana: 0=segunda, 1=terca, 2=quarta, 3=quinta, 4=sexta, 5=sabado, 6=domingo
-- (mesmo padrao do Python datetime.weekday())
CREATE TABLE IF NOT EXISTS public.agenda_regras (
    id BIGSERIAL PRIMARY KEY,
    profissional_id BIGINT NOT NULL REFERENCES public.profissionais(id) ON DELETE RESTRICT,
    ambiente_id BIGINT NOT NULL REFERENCES public.ambientes(id) ON DELETE RESTRICT,
    dia_semana SMALLINT NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio TIME NOT NULL,
    hora_fim TIME NOT NULL,
    data_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    data_fim DATE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_horas_validas CHECK (hora_fim > hora_inicio),
    CONSTRAINT chk_datas_validas CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

CREATE INDEX IF NOT EXISTS idx_agenda_regras_profissional
    ON public.agenda_regras(profissional_id);

CREATE INDEX IF NOT EXISTS idx_agenda_regras_ambiente
    ON public.agenda_regras(ambiente_id);

CREATE INDEX IF NOT EXISTS idx_agenda_regras_dia_ativo
    ON public.agenda_regras(dia_semana, ativo);

ALTER TABLE public.agenda_regras ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin_select_agenda_regras" ON public.agenda_regras;
DROP POLICY IF EXISTS "admin_insert_agenda_regras" ON public.agenda_regras;
DROP POLICY IF EXISTS "admin_update_agenda_regras" ON public.agenda_regras;
DROP POLICY IF EXISTS "admin_delete_agenda_regras" ON public.agenda_regras;

CREATE POLICY "admin_select_agenda_regras"
    ON public.agenda_regras FOR SELECT
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_insert_agenda_regras"
    ON public.agenda_regras FOR INSERT
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_update_agenda_regras"
    ON public.agenda_regras FOR UPDATE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid)
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_delete_agenda_regras"
    ON public.agenda_regras FOR DELETE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);


-- ---------------------------------------------------------------------------
-- 4. TABELA: horario_funcionamento
-- ---------------------------------------------------------------------------
-- Mesma convencao de dia_semana: 0=segunda, ..., 6=domingo
-- Suporta multiplos blocos por dia (ex: Seg 06h-09h + Seg 17h-22h = 2 linhas)
CREATE TABLE IF NOT EXISTS public.horario_funcionamento (
    id BIGSERIAL PRIMARY KEY,
    dia_semana SMALLINT NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio TIME NOT NULL,
    hora_fim TIME NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_func_horas_validas CHECK (hora_fim > hora_inicio)
);

CREATE INDEX IF NOT EXISTS idx_horario_funcionamento_dia
    ON public.horario_funcionamento(dia_semana, ativo);

ALTER TABLE public.horario_funcionamento ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin_select_horario_funcionamento" ON public.horario_funcionamento;
DROP POLICY IF EXISTS "admin_insert_horario_funcionamento" ON public.horario_funcionamento;
DROP POLICY IF EXISTS "admin_update_horario_funcionamento" ON public.horario_funcionamento;
DROP POLICY IF EXISTS "admin_delete_horario_funcionamento" ON public.horario_funcionamento;

CREATE POLICY "admin_select_horario_funcionamento"
    ON public.horario_funcionamento FOR SELECT
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_insert_horario_funcionamento"
    ON public.horario_funcionamento FOR INSERT
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_update_horario_funcionamento"
    ON public.horario_funcionamento FOR UPDATE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid)
    WITH CHECK (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);

CREATE POLICY "admin_delete_horario_funcionamento"
    ON public.horario_funcionamento FOR DELETE
    USING (auth.uid() = 'a5efcb3f-9af5-43fe-a58d-4b61ba2859d8'::uuid);


-- ---------------------------------------------------------------------------
-- 5. DADOS INICIAIS: profissionais
-- ---------------------------------------------------------------------------
-- ON CONFLICT DO NOTHING: se ja existir profissional com mesmo nome (PK violation
-- nao se aplica aqui, mas mantemos a logica defensiva)
-- Como nome NAO e unique, usamos NOT EXISTS pra idempotencia real

INSERT INTO public.profissionais (nome, tipo, cor_hex)
SELECT 'Irmao (Treino)', 'treino', '#2E7D32'
WHERE NOT EXISTS (SELECT 1 FROM public.profissionais WHERE nome = 'Irmao (Treino)');

INSERT INTO public.profissionais (nome, tipo, cor_hex)
SELECT 'Calistenia', 'calistenia', '#90CAF9'
WHERE NOT EXISTS (SELECT 1 FROM public.profissionais WHERE nome = 'Calistenia');

INSERT INTO public.profissionais (nome, tipo, cor_hex)
SELECT 'Kids', 'kids', '#F8BBD0'
WHERE NOT EXISTS (SELECT 1 FROM public.profissionais WHERE nome = 'Kids');


-- ---------------------------------------------------------------------------
-- 6. DADOS INICIAIS: ambientes
-- ---------------------------------------------------------------------------
-- nome e UNIQUE, entao ON CONFLICT funciona

INSERT INTO public.ambientes (nome, area_m2)
VALUES ('Embaixo', 154.00)
ON CONFLICT (nome) DO NOTHING;

INSERT INTO public.ambientes (nome, area_m2)
VALUES ('Em cima', 77.00)
ON CONFLICT (nome) DO NOTHING;


-- ---------------------------------------------------------------------------
-- VERIFICACAO (rodar separadamente para conferir)
-- ---------------------------------------------------------------------------
-- SELECT * FROM public.profissionais ORDER BY id;
-- SELECT * FROM public.ambientes ORDER BY id;
-- SELECT tablename, rowsecurity FROM pg_tables
--   WHERE schemaname = 'public' AND tablename IN
--   ('profissionais', 'ambientes', 'agenda_regras', 'horario_funcionamento');