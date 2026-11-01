# ClipHistory

Histórico de área de transferência para Windows, feito em Python com Tkinter e sem dependências externas. Guarda até 100 textos de até 10.000 caracteres enquanto está rodando e permite buscar, copiar de novo, pausar a captura e limpar tudo.

## Recursos

- Captura automática do clipboard a cada meio segundo
- Busca instantânea no histórico
- Clique duplo (ou `Enter`) para copiar um item de volta
- Tema claro e escuro
- Atalho global `Ctrl+Shift+V` para abrir a janela
- Fechar a janela não encerra o app: ele continua capturando em segundo plano
- Histórico apenas em memória, nada vai para disco ou rede

## Executar

Requer Windows e Python 3 com `tkinter` (já vem no instalador oficial).

```powershell
py .\app.py
```

## Gerar o executável

Com PyInstaller instalado, na pasta do projeto:

```powershell
py -m PyInstaller --noconfirm --clean --onefile --windowed --name ClipHistory --distpath dist-compacto app.py
```

O executável fica em `dist-compacto\ClipHistory.exe`.

## Atalhos

| Atalho | Ação |
| --- | --- |
| `Ctrl+Shift+V` | Abre a janela em qualquer aplicativo |
| `Ctrl+F` | Foca a busca |
| `Enter` | Copia o item selecionado |
| `Esc` | Minimiza a janela |

## Encerrar

O **X** apenas esconde a janela; a captura continua. Para sair de vez, abra **Configurações** e clique em **Sair do ClipHistory**. O histórico é descartado ao sair.

## Privacidade

O histórico fica só na memória do processo e é perdido ao sair. Nada é enviado pela rede nem gravado em arquivo. O app registra apenas texto de até 10.000 caracteres; imagens e textos maiores são ignorados.

Como qualquer histórico de clipboard, ele pode conter informação sensível. Pause a captura antes de copiar algo que não queira manter e limpe o histórico quando precisar.
