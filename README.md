# ClipHistory

Um histórico simples da área de transferência para Windows. O app guarda até 100 textos de até 10.000 caracteres enquanto estiver em execução, permite pesquisar, copiar um item novamente, pausar a captura e limpar o histórico.

Feche a janela (X) e o app continua rodando em segundo plano, capturando normalmente; use `Ctrl+Shift+V` para reabrir. Para encerrar de vez, abra **Aparência** e clique em **Sair do ClipHistory**.

## Executar

Requer Windows e Python 3 com `tkinter` disponível. Não usa dependências externas.

```powershell
py .\app.py
```

## Gerar o executável

Com PyInstaller instalado, na pasta do projeto:

```powershell
py -m PyInstaller --noconfirm --clean --onefile --windowed --name ClipHistory --distpath dist-compacto app.py
```

O executável será criado em `dist-compacto\ClipHistory.exe`.

Em Configurações, escolha entre os modos Claro e Escuro.

Use `Ctrl+Shift+V` para abrir a janela, `Ctrl+F` para buscar e `Esc` para minimizar. Fechar a janela apenas a esconde; a captura continua até você sair pelo menu Aparência.

## Privacidade

- O histórico fica apenas na memória do processo e é descartado ao sair do app (fechar a janela não encerra o processo).
- Nada é enviado pela rede ou gravado em arquivo.
- A captura pode ser pausada; o histórico pode ser limpo a qualquer momento.
- O app registra somente texto de até 10.000 caracteres; imagens e conteúdo maior são ignorados.

Como qualquer histórico de clipboard, ele pode conter texto sensível que você copiou. Pause a captura antes de copiar algo que não queira manter temporariamente e limpe o histórico quando necessário.
