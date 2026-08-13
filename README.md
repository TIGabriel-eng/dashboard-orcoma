# Painel Administrativo - Grupo Orcoma

Sistema de gerenciamento administrativo desenvolvido com Django Admin.

## 🚀 Acesso ao Sistema

**URL:** http://127.0.0.1:8000/admin/

**Credenciais de acesso:**

### Super Admin Principal
- **Usuário:** `ti.orcoma`
- **Senha:** `TIAdmin`
- **Email:** ti@orcoma.com
- **Cargo:** Admin

### Super Admin Alternativo
- **Usuário:** `admin`
- **Senha:** `admin123`
- **Email:** admin@orcoma.com

## 📋 Funcionalidades

### Dashboard Principal
- **Cards de Estatísticas:**
  - Total de Usuários
  - Postagens no Blog
  - Downloads de Ebooks
  - Próximos Eventos

- **Seções:**
  - Usuários Recentes (com status e função)
  - Posts Recentes do Blog
  - Ebooks Populares
  - Calendário de Eventos

### Módulos Administrativos

#### 1. Usuários
- Gerenciamento de administradores
- Controle de cargos (Admin, Editor, Moderador)
- Status ativo/inativo
- Histórico de último login

#### 2. Blog
- Criação e edição de posts
- Sistema de rascunho/publicação
- Controle de visualizações
- Imagens de destaque

#### 3. Ebooks
- Cadastro de materiais
- Controle de downloads
- Status ativo/inativo

#### 4. Eventos
- Gerenciamento de eventos
- Datas de início e término
- Local e link de inscrição
- Filtro de eventos próximos

## 🛠️ Tecnologias

- **Backend:** Django 6.0.6
- **Banco de Dados:** SQLite3
- **Frontend:** HTML, CSS, JavaScript
- **Design:** Custom CSS com design moderno

## 📦 Estrutura do Projeto

```
backend/
├── manage.py
├── orcoma_admin/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/
│   ├── models.py
│   ├── admin.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│   │   └── admin/
│   │       ├── base_site.html
│   │       └── dashboard.html
│   └── populate_data.py
└── static/
    └── css/
        └── admin-custom.css
```

## 🚦 Como Executar

### 1. Instalar dependências
```bash
cd backend
pip install -r requirements.txt
```

### 2. Aplicar migrações
```bash
python manage.py migrate
```

### 3. Criar superusuário
```bash
python manage.py createsuperuser
```

### 4. Popular com dados de exemplo (opcional)
```bash
python core/populate_data.py
```

### 5. Iniciar servidor
```bash
python manage.py runserver
```

### 6. Acessar o admin
Abra o navegador em: http://127.0.0.1:8000/admin/

## 👥 Usuários de Teste

Além do superusuário admin, você pode usar:

| Usuário | Senha | Cargo |
|---------|-------|-------|
| joao.silva | user123 | Moderador |
| maria.santos | user123 | Editor |
| ricardo.oliveira | user123 | Admin |

## 🎨 Design

O painel administrativo possui:
- Design moderno e limpo
- Sidebar com navegação intuitiva
- Cards de estatísticas com ícones
- Tabelas responsivas
- Animações suaves
- Totalmente responsivo

## 📝 Notas

- O servidor de desenvolvimento está rodando em modo DEBUG
- Banco de dados SQLite (db.sqlite3)
- Arquivos estáticos em `/static/`
- Templates customizados em `/core/templates/admin/`

## 🔒 Segurança

**Importante:** Este é um ambiente de desenvolvimento. Para produção:
1. Altere a SECRET_KEY em settings.py
2. Defina DEBUG = False
3. Configure ALLOWED_HOSTS
4. Use um banco de dados mais robusto (PostgreSQL)
5. Configure HTTPS
6. Use um servidor WSGI/ASGI de produção

## 📞 Suporte

Para dúvidas ou problemas, entre em contato com a equipe de desenvolvimento.