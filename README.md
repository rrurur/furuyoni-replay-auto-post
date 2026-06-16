# Furuyoni Replay Auto Post

ふるよにデジタル版デモの `.reply` ファイルを監視し、デッキタイムラインへ自動投稿するWindows向けツールです。

## 使い方

1. `furuyoni_auto_post.exe` を起動します。
2. 初回起動時、自動投稿が有効化されます。
3. 以後、Windows起動時に自動で監視します。
4. もう一度 `furuyoni_auto_post.exe` を起動すると、次の確認が出ます。

```text
自動投稿は有効です。無効化しますか？ (Y/N)
```

`Y` を入力すると自動投稿を無効化します。

## 投稿される情報

- Steam名をもとにした表示名: `Steam名(steam)`
- 自分のメガミ
- 相手のメガミ
- 初期デッキ10枚
- 勝敗
- 対戦日時
- 環境: 起源戦

## 投稿しない情報

- `.reply` ファイルそのもの
- 全リプレイログ
- ライフやオーラの推移
- 手札推移
- 相手のデッキ

## 保存場所

設定、ログ、投稿済み管理情報は次のフォルダに保存されます。

```text
%APPDATA%\FuruyoniReplayAutoPost
```

## 自分でビルドする場合

Python 3.12以上を用意し、次を実行します。

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File build\build_exe.ps1
```

生成物は `dist\furuyoni_auto_post.exe` です。
