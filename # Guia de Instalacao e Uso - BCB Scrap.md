# Guia de Instalacao e Uso - BCB Scraper

## Pre-requisitos

### 1. Instalar Python 3.7+
- Download: https://python.org/downloads/
- No Windows: marcar "Add Python to PATH" durante instalacao

### 2. Instalar bibliotecas necessarias

```bash
pip install requests beautifulsoup4 pandas lxml
```

OU usando requirements.txt:

```bash
pip install -r requirements.txt
```

## Arquivos Disponi­veis

### 1. `bcb_scraper.py` (Versao Completa)
- Script completo com logging
- Controle de erros avancado  
- Configuracoes customizaveis
- Processamento de todos os documentos do CSV

### 2. `bcb_scraper_simple.py` (Versao Simples)
- Script minimalista
- Apenas bibliotecas essenciais
- Mais facil de entender e modificar
- Processa documentos prioritarios se CSV nao existir

### 3. `normativos_spb_bcb.csv`
- Lista completa dos documentos
- URLs e metadados
- Usado pelos scripts para saber quais documentos baixar

## Como Usar

### Opcao 1: Script Completo

```bash
python bcb_scraper.py
```

- Digite o delay desejado entre requisicoes (recomendado: 2 segundos)
- Aguarde o processamento
- Arquivos serao salvos em `normativos_txt/`

### Opcao 2: Script Simples

```bash
python bcb_scraper_simple.py
```

- Processa automaticamente
- Arquivos serao salvos em `normativos/`

## Estrutura dos Arquivos Gerados

Cada arquivo .txt tera:
```
# Resolucao BCB nº 1
# URL: https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolucao%20BCB&numero=1
# Data: 11/09/2025 17:53:45
# ==================================================

[CONTEuDO DO DOCUMENTO AQUI]
```

## Dicas Importantes

### 1. Seja Respeitoso
- Use delay de pelo menos 2 segundos entre requisicoes
- Nao execute multiplas insti¢ncias simultaneamente
- O BCB pode bloquear IPs que fazem muitas requisicoes

### 2. Verificar Conteudo
- Alguns documentos podem ter layouts diferentes
- Verifique se o texto extrai­do esta completo
- Em caso de problemas, acesse manualmente a URL

### 3. Organizacao
- Arquivos sao nomeados automaticamente
- Documentos similares ficam juntos quando ordenados
- Evite caracteres especiais nos nomes

## Documentos Prioritarios

Se quiser comecar apenas com os mais importantes:

1. **Resolucao BCB nº 1** - Regulamento do Pix
2. **Resolucao BCB nº 150** - Arranjos de pagamento consolidados
3. **Resolucao CMN nº 4.282** - Marco legal do SPB
4. **Circular nº 3.682** - Regulamento operacional base
5. **Resolucao BCB nº 195** - Sistema de Pagamentos Instanti¢neos

## Solucao de Problemas

### Erro: "Module not found"
```bash
pip install [nome-do-modulo]
```

### Erro: "Permission denied"
- Execute como administrador (Windows)
- Use `sudo` (Linux/Mac)
- Verifique permissoes da pasta

### Erro: "Connection timeout"
- Verifique sua conexao com internet
- Aumente o delay entre requisicoes
- Tente novamente mais tarde

### Conteudo incompleto
- Acesse manualmente a URL do documento
- Verifique se o site do BCB esta funcionando
- Alguns documentos podem ter protecao adicional

## Para Usar no Google NotebookLM

1. Execute o scraper
2. Acesse a pasta com os arquivos .txt
3. Selecione os documentos desejados
4. Faca upload no NotebookLM como "Sources"
5. O NotebookLM processara automaticamente o conteudo