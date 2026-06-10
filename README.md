# 🚁 Simulador de Eventos Discretos — Air Tesourinha (Eixão-UAM)

Simulador de Eventos Discretos (DES) para uma estrutura individual de **Air Tesourinha** do corredor de mobilidade aérea urbana **Eixão-UAM**, em Brasília. Desenvolvido no Departamento de Ciência da Computação da Universidade de Brasília (UnB).

---

## Visão Geral

O corredor **Eixão-UAM** é uma infraestrutura aérea urbana proposta para a faixa central de 45 metros do Eixão de Brasília, organizada em camadas verticais para diferentes classes de Veículos Aéreos Não Tripulados (UAVs). As **Air Tesourinhas** são interseções aéreas locais que viabilizam manobras de pouso, decolagem, troca de via e mudança de sentido — sem interromper o fluxo contínuo de cruzeiro nas vias principais.

Este simulador modela o comportamento temporal e operacional de **uma única Air Tesourinha**, operando em **um único sentido de tráfego**, através de uma Simulação de Eventos Discretos puramente matemática (sem representação visual, sem física de voo, sem clima).

### Objetivos

1. **Viabilidade operacional**: demonstrar que o modelo de Air Tesourinha suporta densidades realistas de tráfego aéreo urbano.
2. **Densidade crítica (λ\*)**: identificar o limiar a partir do qual ocorrem bloqueios físicos nas vias principais.
3. **Métricas de desempenho**: quantificar *throughput*, *delay*, ocupação de *buffers* e eventos de *spillback* via análise estatística.

---

## Descrição do Código

O simulador (`simulation.py`) é construído sobre o framework **SimPy** e organizado em três blocos principais:

### Classes de Domínio

- **`Config`** — encapsula os parâmetros cinemáticos dependentes da velocidade de interseção (headway de cruzeiro, headway de merge, limiares de backpressure). Suporta configurações para 10 m/s e 15 m/s.
- **`Drone`** — representa um UAV individual com seu ID, via de origem, plano de voo atribuído e timestamps de rastreamento (entrada/saída de buffers).
- **`AirTesourinha`** — modela toda a infraestrutura da interseção: os quatro *buffers* (`simpy.Store`), o vertistop, os *locks* de merge por via (`simpy.Resource`), os contadores de métricas e a lógica de backpressure.

### Processos SimPy

- **`inpoint_generator()`** — processo contínuo que gera drones nas vias A e B aplicando backpressure dinâmico.
- **`buffer_in_generator()`** — processo que gera drones oriundos da via oposta (Buffer IN).
- **`vertistop_manager()`** — processo responsável pelas decolagens e pela simulação de rotação humana (flutuação de ocupação) no Vertistop.
- **`drone_lifecycle()`** — executa a rota completa do drone conforme seu plano de voo (Cruise, Descend, Switch, Return OUT, etc.), coordenando o tráfego nos buffers e os _locks_ de _merge_.

### Backpressure Dinâmico

Drones são gerados por processos independentes em diferentes origens (Inpoint Via A, Inpoint Via B, e Buffer IN), além das decolagens do Vertistop, respeitando regras de \textit{headway} e restrições da via. Os planos de voo incluem:

- **Cruise**: travessia direta (sem manobras)
- **Descend**: pouso no vertistop via Descend Buffer
- **Switch**: troca de via (A ↔ B)
- **Return OUT**: saída para via de sentido oposto
- **Rotas de Buffer IN**: inserção nas vias ou descida
- **Decolagens**: inserção via elevador para as vias ou retorno

Quando um buffer atinge 100%, o drone fica retido no nó de diverge, gerando *spillback* (fila retrógrada até o Inpoint).

### Grid Search Comparativo

A função `run_comparative_grid_search()` executa a bateria de experimentos: varre densidades de entrada e velocidades de interseção, com múltiplas replicações estocásticas, e gera o gráfico comparativo em `logs/comparacao_velocidades.png`.

---

## Pré-requisitos

- **Python** 3.10+
- **pip**

### Dependências

| Pacote       | Uso                                     |
| ------------ | --------------------------------------- |
| `simpy`      | Motor de Simulação de Eventos Discretos |
| `numpy`      | Cálculos estatísticos                   |
| `pandas`     | Estruturação e exportação de dados      |
| `matplotlib` | Geração de gráficos                     |

---

## Instalação

```bash
git clone https://github.com/vmg192/simu_tesourinha
cd simu_tesourinha
python3 -m venv .venv
source .venv/bin/activate
pip install simpy numpy pandas matplotlib
```

---

## Execução

```bash
source .venv/bin/activate
python simulation.py
```

A simulação roda automaticamente os seguintes cenários:

- **Velocidades**: 10 m/s e 15 m/s
- **Densidades de entrada**: 500, 800, 1100, 1400, 1700 e 2000 drones/hora
- **Replicações**: 10 rodadas estocásticas por cenário
- **Duração por rodada**: 4 horas simuladas (14.400 s)

O progresso é exibido no terminal. Ao final, o gráfico comparativo é salvo em `logs/comparacao_velocidades.png`.

### Parâmetros Configuráveis

Os parâmetros podem ser ajustados diretamente em `simulation.py`:

| Parâmetro                | Onde                             | Valores padrão                          |
| ------------------------ | -------------------------------- | --------------------------------------- |
| Comprimento da tesourinha | `TES_LENGTH`                    | 60.0 m                                  |
| Tempo de descida/subida  | `DESCEND_TIME`, `ASCEND_TIME`    | 33.0 s                                  |
| Capacidades dos buffers  | Dicionário `CAPACITIES`          | descend=21, switch=16, IN=10, OUT=10    |
| Planos de voo            | `PROB_CRUISE`, `PROB_DESCEND`, etc. | 0.65, 0.12, 0.115, 0.115            |
| Densidades do grid       | `densities` em `run_comparative_grid_search()` | [500, 800, 1100, 1400, 1700, 2000] |
| Replicações              | `replications`                   | 10                                       |
| Duração da simulação     | `sim_time`                       | 14400 s (4h)                             |

---

## Documentação Técnica

A formalização matemática completa do modelo — incluindo a derivação do *geofencing* dinâmico, fórmulas de *headway*, lógica de congestionamento, desenho experimental e análise de resultados — está disponível no relatório:

📄 **[`relatorio_simulacao.tex`](relatorio_simulacao.tex)** — *Modelo de Simulação de Eventos Discretos para a Air Tesourinha do Corredor Eixão-UAM*

---

> **Universidade de Brasília** — Departamento de Ciência da Computação
> Projeto Eixão-UAM
