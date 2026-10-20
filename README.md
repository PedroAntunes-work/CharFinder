# CharFinder

O CharFinder é um aplicativo desktop para Windows que ajuda a localizar caracteres potencialmente incompatíveis em arquivos XML e a salvar uma cópia com as correções escolhidas pelo usuário. A análise é feita localmente, não exige um XSD e não altera o arquivo original.

## Funcionalidades

- Analisa arquivos XML e identifica caracteres proibidos pelo XML 1.0 e caracteres cobertos por regras conhecidas.
- Sinaliza alguns casos suspeitos de codificação Windows-1252 em arquivos declarados como ISO-8859-1. Essa verificação é heurística, não confirma a causa de uma rejeição.
- Apresenta sugestões sem aplicá-las automaticamente; o usuário pode escolher uma substituição, definir uma regra personalizada ou remover o caractere.
- Salva uma cópia corrigida, preservando a codificação e os demais bytes sempre que possível. O original não pode ser sobrescrito.
- Mantém regras personalizadas em `character-exceptions.json`, considerando o caractere e os bytes de origem.

Consulte o [manual do usuário](docs/LEIAME.html) para instruções detalhadas de uso.

## Requisitos

- Python 3.12 ou superior.
- Windows para executar a interface gráfica e gerar o executável. Os testes do analisador podem ser executados em ambientes com Python e as dependências instaladas.
- Git para clonar o repositório e preparar alterações.

## Clonar e configurar

Clone o repositório com a URL correspondente:

```powershell
git clone https://github.com/...
cd CharFinder
```

Crie e ative um ambiente virtual, instale o projeto com as dependências de teste e execute a aplicação:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python charfinder.py
```

Se a política do PowerShell impedir a ativação do ambiente virtual, use diretamente o interpretador dele:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe charfinder.py
```

## Executar os testes

Com as dependências de teste instaladas:

```powershell
python -m pytest
```

Os testes estão em `tests/`. Ao alterar o analisador ou o fluxo de correção, acrescente ou atualize testes para cobrir o comportamento afetado.

## Contribuir e abrir um Pull Request

1. Confira as issues e os PRs existentes para verificar se o assunto já está em discussão.
2. Crie uma branch a partir da branch principal atualizada (o exemplo usa `main`; ajuste o nome se o repositório usar outro):

   ```powershell
   git switch main
   git pull
   git switch -c tipo/resumo-da-alteracao
   ```

   Use um nome curto e descritivo, por exemplo `fix/xml-offset` ou `docs/setup`.
3. Faça uma alteração focada e mantenha a compatibilidade com os fluxos existentes. Para mudanças no comportamento, atualize os testes e a documentação relacionada.
4. Execute `python -m pytest` e confira o diff antes de enviar:

   ```powershell
   git diff --check
   git status
   git diff
   ```
5. Faça push da branch e abra um Pull Request para a branch principal do projeto. Descreva o problema e a solução, registre como validou a mudança e inclua imagens quando forem úteis para alterações na interface.

Não inclua executáveis, arquivos gerados em `build/` ou `dist/`, caches, ambientes virtuais, arquivos XML de terceiros ou dados que não devam ser publicados. O `.gitignore` cobre os artefatos locais comuns; revise sempre o conteúdo do PR antes de enviá-lo.

## Estrutura do projeto

```text
.
├── assets/                 # Ícone e metadados de versão do executável
├── docs/                   # Manual do usuário
├── scripts/                # Build, preparação Tcl/Tk e instalação no Windows
├── tests/                  # Testes automatizados
├── character-exceptions.json
├── charfinder.py           # Interface gráfica
├── xml_analyzer.py         # Análise e correção de XML
├── CharFinder.spec         # Configuração alternativa do PyInstaller
└── pyproject.toml          # Metadados, dependências e configuração do pytest
```

`build/`, `dist/`, caches e ambientes virtuais são diretórios/arquivos locais gerados e não devem ser versionados.

## Gerar o executável no Windows

Para instalar as dependências de empacotamento e gerar `dist\CharFinder.exe`, execute:

```powershell
scripts\build_exe.bat
```

O script prepara os dados Tcl/Tk, empacota o aplicativo com PyInstaller e copia para `dist/` o manual, o catálogo e os scripts de instalação. Essa etapa é opcional para desenvolvimento e não é necessária para executar os testes.

Os dois scripts de configuração ficam em `dist/` e instalam o executável, mas têm finalidades diferentes:

- `configurar_charfinder.bat` instala ou atualiza a versão normal em `C:\Charfinder` e cria o atalho `CharFinder` na área de trabalho.
- `configurar_charfinder_homologa.bat` instala ou atualiza uma cópia isolada para testes em `C:\CharFinder_Homologa` e cria o atalho `CharFinder_Homologa`. Essa pasta permite testar a versão sem alterar a instalação normal em `C:\Charfinder`.

Para distribuir, copie o conteúdo de `dist/` para uma pasta compartilhada e execute o script correspondente ao tipo de instalação desejado.
