import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes, ConversationHandler)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename):
    with open(os.path.join(BASE_DIR, filename), encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(os.path.join(BASE_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DEPARTEMENTS = load_json("departements.json")
PROFILS = load_json("profils.json")
CONFIG = load_json("config.json")
SKAM = load_json("skam.json")
PROMOS = load_json("promos.json")

SECRET_CODE = "STONNABIS"
ADMIN_CODE  = "Luphima6274"
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

# Utilisateurs déverrouillés (en mémoire)
UNLOCKED_USERS = set()
ADMIN_USERS    = set()

# États conversation
(WAIT_CODE, CERTIF_PSEUDO, CERTIF_PLUG_NOM, CERTIF_PLUG_LIEN,
 CERTIF_GAMME, CERTIF_PRIX, CERTIF_LIVRAISON,
 ADMIN_WAIT_DEP, ADMIN_WAIT_NOM, ADMIN_WAIT_LIEN,
 ADMIN_WAIT_CERTIFIED,
 ADMIN_SUPPR_NOM,
 SKAM_WAIT_NOM, SKAM_WAIT_LIEN,
 PROMO_WAIT_NOM, PROMO_WAIT_EMOJI, PROMO_WAIT_CODE, PROMO_WAIT_REDUC, PROMO_WAIT_LIEN) = range(20)

CERTIF_QUESTIONS = [
    ("pseudo",     "👤 Ton *pseudo Telegram* ?",              "@ton_pseudo"),
    ("plug_nom",   "🏷️ *Nom du plug* à certifier ?",          "Nom ou pseudo"),
    ("plug_lien",  "🔗 *Lien du plug ou menu* ?",             "t.me/... ou lien"),
    ("gamme",      "🌿 *Gamme de référence* ?",               "CBD fleur, résine…"),
    ("prix_min",   "💶 *Prix minimum* pratiqué ?",            "Ex : à partir de 10€"),
    ("livraison",  "📦 *Livraison ou envoi postal ?*",        "Livraison / Postal / Les deux"),
]

# ── Notif admin ──────────────────────────────────────────────────────────
async def notify_admin(context, text):
    if ADMIN_CHAT_ID:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")

# ── /start → demande le code ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in UNLOCKED_USERS or user_id in ADMIN_USERS:
        await show_menu(update, context)
        return ConversationHandler.END
    await update.message.reply_text(
        "🍀 *La Note Verte*\n\n"
        "👋 Salut !\n\n"
        "Ici on certifie les meilleurs plugs de France — testés et approuvés par nos équipes. "
        "Tu trouveras forcément ton plug préféré 😎\n\n"
        "Si il n'y est pas, hésite pas à contacter nos équipes pour faire certifier ton plug.\n\n"
        "🔐 Entre ton code d'accès pour continuer :",
        parse_mode="Markdown"
    )
    return WAIT_CODE

async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    if code == ADMIN_CODE:
        ADMIN_USERS.add(user_id)
        UNLOCKED_USERS.add(user_id)
        await update.message.reply_text("✅ Code admin accepté ! Tape /admin pour gérer le bot.")
        await show_menu(update, context)
        return ConversationHandler.END
    elif code.upper() == SECRET_CODE:
        UNLOCKED_USERS.add(user_id)
        await update.message.reply_text("✅ Accès accordé ! Bienvenue 🍀")
        await show_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Code incorrect. Réessaie :")
        return WAIT_CODE

# ── Menu principal ───────────────────────────────────────────────────────
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Liste Certified", callback_data="menu_certified"),
         InlineKeyboardButton("📞 Contact",         callback_data="menu_contact")],
        [InlineKeyboardButton("📋 Liste SK-AM",     callback_data="menu_skam"),
         InlineKeyboardButton("🌐 Nos Réseaux",     callback_data="menu_reseaux")],
        [InlineKeyboardButton("🎁 Concours",        callback_data="menu_concours"),
         InlineKeyboardButton("🏷️ Code Promo",      callback_data="menu_promo")],
        [InlineKeyboardButton("📍 Trouver un profil près de moi", callback_data="geo_start")],
        [InlineKeyboardButton("🏅 Se faire certifier / Certifier son plug", callback_data="certif_start")],
    ]
    text = f"*{CONFIG['nom_bot']}*\n\n{CONFIG['description']}\n\nChoisis une option :"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in UNLOCKED_USERS and user_id not in ADMIN_USERS:
        await update.message.reply_text("🔐 Entre d'abord ton code avec /start")
        return
    await show_menu(update, context)

# ── Certification ────────────────────────────────────────────────────────
async def certif_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in UNLOCKED_USERS and user_id not in ADMIN_USERS:
        await query.edit_message_text("🔐 Tape /start pour accéder au bot.")
        return ConversationHandler.END
    context.user_data["certif"] = {}
    context.user_data["certif_step"] = 0
    _, question, exemple = CERTIF_QUESTIONS[0]
    await query.edit_message_text(
        f"🏅 *Demande de certification* — Étape 1/6\n\n{question}\n\n_(ex : {exemple})_\n\n"
        "_(Tape /annuler pour quitter)_",
        parse_mode="Markdown"
    )
    return CERTIF_PSEUDO

async def certif_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("certif_step", 0)
    key = CERTIF_QUESTIONS[step][0]
    context.user_data["certif"][key] = update.message.text
    next_step = step + 1
    context.user_data["certif_step"] = next_step
    if next_step < len(CERTIF_QUESTIONS):
        _, question, exemple = CERTIF_QUESTIONS[next_step]
        await update.message.reply_text(
            f"*Étape {next_step+1}/6 :*\n\n{question}\n\n_(ex : {exemple})_",
            parse_mode="Markdown"
        )
        return next_step
    else:
        data = context.user_data["certif"]
        user = update.effective_user
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        recap = (
            "✅ *Demande envoyée !*\n\n"
            "━━━━━━━━━━━━━━━━\n"
            f"👤 *Pseudo :* {data.get('pseudo','—')}\n"
            f"🏷️ *Plug :* {data.get('plug_nom','—')}\n"
            f"🔗 *Lien :* {data.get('plug_lien','—')}\n"
            f"🌿 *Gamme :* {data.get('gamme','—')}\n"
            f"💶 *Prix min :* {data.get('prix_min','—')}\n"
            f"📦 *Livraison :* {data.get('livraison','—')}\n"
            "━━━━━━━━━━━━━━━━\n"
            "Notre équipe te recontactera rapidement. Merci ! 🍀"
        )
        keyboard = [[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]
        await update.message.reply_text(recap, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        notif = (
            "🏅 *Nouvelle demande de certification !*\n"
            "━━━━━━━━━━━━━━━━\n"
            f"👤 *Pseudo :* {data.get('pseudo','—')}\n"
            f"🏷️ *Plug :* {data.get('plug_nom','—')}\n"
            f"🔗 *Lien :* {data.get('plug_lien','—')}\n"
            f"🌿 *Gamme :* {data.get('gamme','—')}\n"
            f"💶 *Prix min :* {data.get('prix_min','—')}\n"
            f"📦 *Livraison :* {data.get('livraison','—')}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"📩 *Envoyé par :* {username}"
        )
        await notify_admin(context, notif)
        context.user_data.pop("certif", None)
        context.user_data.pop("certif_step", None)
        return ConversationHandler.END

async def certif_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("certif", None)
    await update.message.reply_text("❌ Demande annulée. Tape /menu pour revenir.")
    return ConversationHandler.END

# ── COMMANDES ADMIN ──────────────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    await update.message.reply_text(
        "⚙️ *Panel Admin — La Note Verte*\n\n"
        "Commandes disponibles :\n\n"
        "➕ */ajout* — Ajouter un profil\n"
        "🗑️ */suppr* — Supprimer un profil\n"
        "📋 */liste_dep* `XX` — Voir les profils d'un département\n"
        "📊 */stats* — Voir les stats du bot\n\n"
        "_Ex : /liste\\_dep 75_",
        parse_mode="Markdown"
    )

# ── /ajout ───────────────────────────────────────────────────────────────
async def ajout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return ConversationHandler.END
    await update.message.reply_text("➕ *Ajout de profil*\n\nNuméro du département ? _(ex: 75, 13, 69)_", parse_mode="Markdown")
    return ADMIN_WAIT_DEP

async def ajout_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_dep"] = update.message.text.strip()
    await update.message.reply_text("👤 Nom du profil ?")
    return ADMIN_WAIT_NOM

async def ajout_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_nom"] = update.message.text.strip()
    await update.message.reply_text("📍 Ville ?")
    return ADMIN_WAIT_VILLE

async def ajout_ville(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_ville"] = update.message.text.strip()
    await update.message.reply_text("📝 Description ? _(ou tape - pour passer)_", parse_mode="Markdown")
    return ADMIN_WAIT_DESC

async def ajout_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_desc"] = "" if val == "-" else val
    await update.message.reply_text("📬 Contact Telegram ? _(ex: @pseudo ou - pour passer)_", parse_mode="Markdown")
    return ADMIN_WAIT_CONTACT

async def ajout_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_contact"] = "" if val == "-" else val
    await update.message.reply_text("✅ Certified ? Tape *oui* ou *non*", parse_mode="Markdown")
    return ADMIN_WAIT_CERTIFIED

async def ajout_certified(update: Update, context: ContextTypes.DEFAULT_TYPE):
    certified = update.message.text.strip().lower() in ["oui", "yes", "o"]
    dep = context.user_data["new_dep"]
    profil = {
        "nom":         context.user_data["new_nom"],
        "ville":       context.user_data["new_ville"],
        "certified":   certified,
        "description": context.user_data["new_desc"],
        "contact":     context.user_data["new_contact"],
    }
    if dep not in PROFILS:
        PROFILS[dep] = []
    PROFILS[dep].append(profil)
    save_json("profils.json", PROFILS)
    badge = "✅" if certified else "—"
    await update.message.reply_text(
        f"✅ *Profil ajouté !*\n\n"
        f"👤 {profil['nom']} — {profil['ville']} ({dep})\n"
        f"Certified : {badge}",
        parse_mode="Markdown"
    )
    for k in ["new_dep","new_nom","new_ville","new_desc","new_contact"]:
        context.user_data.pop(k, None)
    return ConversationHandler.END

# ── /suppr ───────────────────────────────────────────────────────────────
async def suppr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return ConversationHandler.END
    await update.message.reply_text("🗑️ *Suppression*\n\nNuméro du département ?", parse_mode="Markdown")
    return ADMIN_SUPPR_DEP

async def suppr_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dep = update.message.text.strip()
    profils_dep = PROFILS.get(dep, [])
    if not profils_dep:
        await update.message.reply_text(f"😕 Aucun profil dans le département {dep}.")
        return ConversationHandler.END
    context.user_data["suppr_dep"] = dep
    liste = "\n".join([f"*{i+1}.* {p['nom']} — {p['ville']}" for i, p in enumerate(profils_dep)])
    await update.message.reply_text(
        f"📋 Profils dans le *{dep}* :\n\n{liste}\n\nTape le *numéro* à supprimer :",
        parse_mode="Markdown"
    )
    return ADMIN_SUPPR_IDX

async def suppr_idx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dep = context.user_data["suppr_dep"]
    try:
        idx = int(update.message.text.strip()) - 1
        profil = PROFILS[dep][idx]
        PROFILS[dep].pop(idx)
        save_json("profils.json", PROFILS)
        await update.message.reply_text(f"✅ *{profil['nom']}* supprimé du département {dep}.", parse_mode="Markdown")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Numéro invalide. Annulé.")
    return ConversationHandler.END

# ── /liste_dep ───────────────────────────────────────────────────────────
async def liste_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage : /liste_dep 75")
        return
    dep = args[0].strip()
    profils_dep = PROFILS.get(dep, [])
    if not profils_dep:
        await update.message.reply_text(f"Aucun profil dans le département {dep}.")
        return
    lines = [f"📋 *Profils — {dep}* ({len(profils_dep)}) :\n"]
    for i, p in enumerate(profils_dep):
        badge = "✅" if p.get("certified") else "○"
        lines.append(f"{badge} *{i+1}. {p['nom']}* — {p.get('ville','?')}\n   📬 {p.get('contact','—')}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── /stats ───────────────────────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    total = sum(len(v) for v in PROFILS.values())
    certified = sum(1 for v in PROFILS.values() for p in v if p.get("certified"))
    deps = len([d for d, v in PROFILS.items() if v])
    await update.message.reply_text(
        f"📊 *Stats La Note Verte*\n\n"
        f"👥 Profils total : *{total}*\n"
        f"✅ Certified : *{certified}*\n"
        f"📍 Départements actifs : *{deps}*\n"
        f"🔓 Utilisateurs connectés : *{len(UNLOCKED_USERS)}*",
        parse_mode="Markdown"
    )

# ── /get_my_id ───────────────────────────────────────────────────────────
async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔑 Ton Chat ID : `{update.effective_user.id}`", parse_mode="Markdown")

# ── Géolocalisation ──────────────────────────────────────────────────────
async def geo_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    regions = {}
    for dep_num, dep_data in DEPARTEMENTS.items():
        r = dep_data["region"]
        regions.setdefault(r, []).append((dep_num, dep_data["nom"]))
    keyboard = [[InlineKeyboardButton(f"📌 {r}", callback_data=f"region_{r}")] for r in sorted(regions)]
    keyboard.append([InlineKeyboardButton("🏠 Retour", callback_data="home")])
    await query.edit_message_text("🗺️ *Choisis ta région :*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_departements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_name = query.data.replace("region_", "")
    deps = sorted([(n, d["nom"]) for n, d in DEPARTEMENTS.items() if d["region"] == region_name])
    keyboard = [[InlineKeyboardButton(f"{n} – {nom}", callback_data=f"dep_{n}")] for n, nom in deps]
    keyboard.append([InlineKeyboardButton("◀️ Régions", callback_data="geo_start")])
    await query.edit_message_text(f"📍 *{region_name}*\nChoisis ton département :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profils(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dep_num = query.data.replace("dep_", "")
    dep_nom = DEPARTEMENTS.get(dep_num, {}).get("nom", dep_num)
    region  = DEPARTEMENTS.get(dep_num, {}).get("region", "")
    profils_dep = PROFILS.get(dep_num, [])
    if not profils_dep:
        keyboard = [[InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")]]
        await query.edit_message_text(f"😕 Aucun profil pour *{dep_nom}* ({dep_num}) pour le moment.\n\nHésite pas à contacter nos équipes ! 🍀", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    keyboard = [[InlineKeyboardButton(f"{'✅ ' if p.get('certified') else ''}{p['nom']}", callback_data=f"profil_{dep_num}_{i}")] for i, p in enumerate(profils_dep)]
    keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")])
    await query.edit_message_text(f"👥 *{dep_nom} ({dep_num})*\n{len(profils_dep)} profil(s)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profil_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, dep_num, idx_str = query.data.split("_", 2)
    p = PROFILS[dep_num][int(idx_str)]
    lines = []
    if p.get("certified"): lines.append("✅ *CERTIFIED*")
    lines.append(f"👤 *{p['nom']}*")
    lines.append(f"📍 {p.get('ville','N/A')} ({dep_num})")
    if p.get("description"): lines.append(f"\n_{p['description']}_")
    if p.get("contact"):     lines.append(f"\n📬 {p['contact']}")
    keyboard = [[InlineKeyboardButton("◀️ Retour", callback_data=f"dep_{dep_num}")]]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ── Pages statiques ──────────────────────────────────────────────────────
async def handle_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    back = [[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]
    pages = {
        "menu_certified": CONFIG.get("texte_certified",""),
        "menu_contact":   CONFIG.get("texte_contact",""),
        "menu_reseaux":   CONFIG.get("texte_reseaux",""),
        "menu_concours":  "⚙️⏳⌛️\n\n*Concours en cours de préparation…*\n\nReviens bientôt !",
    }

    if action in pages:
        await query.edit_message_text(pages[action], reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")

    elif action == "menu_skam":
        if not SKAM:
            await query.edit_message_text("📋 *Liste SK-AM*\n\nAucun membre pour le moment.", reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(m["nom"], url=m["lien"])] for m in SKAM]
        keyboard.append([InlineKeyboardButton("🏠 Accueil", callback_data="home")])
        await query.edit_message_text(
            "📋 *Liste SK-AM*\n\nClique sur un membre pour accéder à son lien :",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif action == "menu_promo":
        if not PROMOS:
            await query.edit_message_text("🏷️ *Codes Promo*\n\nAucun partenaire pour le moment.", reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(f"{p['emoji']} {p['nom']}", callback_data=f"promo_{i}")] for i, p in enumerate(PROMOS)]
        keyboard.append([InlineKeyboardButton("🏠 Accueil", callback_data="home")])
        await query.edit_message_text(
            "🏷️ *Codes Promo — Nos Partenaires*\n\nChoisis un partenaire :",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif action.startswith("promo_"):
        idx = int(action.replace("promo_", ""))
        p = PROMOS[idx]
        keyboard = [
            [InlineKeyboardButton("🔗 Visiter le site", url=p["lien"])],
            [InlineKeyboardButton("◀️ Partenaires", callback_data="menu_promo")],
        ]
        await query.edit_message_text(
            f"{p['emoji']} *{p['nom']}*\n\n"
            f"💰 {p['reduction']}\n\n"
            f"🏷️ Code promo :\n`{p['code']}`\n\n"
            f"_(Appuie longuement sur le code pour le copier)_",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif action == "home":
        await show_menu(update, context)

# ── Admin SK-AM ──────────────────────────────────────────────────────────
async def ajout_skam_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return ConversationHandler.END
    await update.message.reply_text("📋 *Ajout SK-AM*\n\nNom du membre ?", parse_mode="Markdown")
    return SKAM_WAIT_NOM

async def ajout_skam_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["skam_nom"] = update.message.text.strip()
    await update.message.reply_text("🔗 Lien Telegram du membre ? _(ex: https://t.me/pseudo)_", parse_mode="Markdown")
    return SKAM_WAIT_LIEN

async def ajout_skam_lien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SKAM.append({"nom": context.user_data["skam_nom"], "lien": update.message.text.strip()})
    save_json("skam.json", SKAM)
    await update.message.reply_text(f"✅ *{context.user_data['skam_nom']}* ajouté à la liste SK-AM !", parse_mode="Markdown")
    return ConversationHandler.END

async def suppr_skam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    args = context.args
    if not args:
        liste = "\n".join([f"*{i+1}.* {m['nom']}" for i, m in enumerate(SKAM)])
        await update.message.reply_text(f"📋 Liste SK-AM actuelle :\n\n{liste}\n\nUsage : /suppr\_skam `nom exact`", parse_mode="Markdown")
        return
    nom = " ".join(args).strip()
    idx = next((i for i, m in enumerate(SKAM) if m["nom"].lower() == nom.lower()), None)
    if idx is None:
        await update.message.reply_text(f"😕 Membre *{nom}* introuvable.", parse_mode="Markdown")
        return
    SKAM.pop(idx)
    save_json("skam.json", SKAM)
    await update.message.reply_text(f"✅ *{nom}* supprimé de la liste SK-AM.", parse_mode="Markdown")

# ── Admin Promos ──────────────────────────────────────────────────────────
async def ajout_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return ConversationHandler.END
    await update.message.reply_text("🏷️ *Ajout partenaire*\n\nNom du commerçant ?", parse_mode="Markdown")
    return PROMO_WAIT_NOM

async def ajout_promo_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_nom"] = update.message.text.strip()
    await update.message.reply_text("Emoji ? _(ex: 🛍️ ou - pour défaut)_", parse_mode="Markdown")
    return PROMO_WAIT_EMOJI

async def ajout_promo_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["promo_emoji"] = "🏪" if val == "-" else val
    await update.message.reply_text("Code promo ?")
    return PROMO_WAIT_CODE

async def ajout_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_code"] = update.message.text.strip()
    await update.message.reply_text("Description réduction ? _(ex: -15% sur tout)_", parse_mode="Markdown")
    return PROMO_WAIT_REDUC

async def ajout_promo_reduc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_reduc"] = update.message.text.strip()
    await update.message.reply_text("🔗 Lien du site ? _(ex: https://site.fr)_", parse_mode="Markdown")
    return PROMO_WAIT_LIEN

async def ajout_promo_lien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    PROMOS.append({
        "nom": context.user_data["promo_nom"],
        "emoji": context.user_data["promo_emoji"],
        "code": context.user_data["promo_code"],
        "reduction": context.user_data["promo_reduc"],
        "lien": update.message.text.strip(),
    })
    save_json("promos.json", PROMOS)
    await update.message.reply_text(f"✅ Partenaire *{context.user_data['promo_nom']}* ajouté !", parse_mode="Markdown")
    return ConversationHandler.END

async def suppr_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    args = context.args
    if not args:
        liste = "\n".join([f"*{i+1}.* {p['emoji']} {p['nom']}" for i, p in enumerate(PROMOS)])
        await update.message.reply_text(f"🏷️ Partenaires actuels :\n\n{liste}\n\nUsage : /suppr\_promo `nom exact`", parse_mode="Markdown")
        return
    nom = " ".join(args).strip()
    idx = next((i for i, p in enumerate(PROMOS) if p["nom"].lower() == nom.lower()), None)
    if idx is None:
        await update.message.reply_text(f"😕 Partenaire *{nom}* introuvable.", parse_mode="Markdown")
        return
    PROMOS.pop(idx)
    save_json("promos.json", PROMOS)
    await update.message.reply_text(f"✅ *{nom}* supprimé des partenaires.", parse_mode="Markdown")

# ── Main ─────────────────────────────────────────────────────────────────
def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN manquant !")

    app = Application.builder().token(TOKEN).build()

    # Conversation : code d'accès
    code_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_code)] },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    # Conversation : certification
    certif_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(certif_start, pattern="^certif_start$")],
        states={
            CERTIF_PSEUDO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_PLUG_NOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_PLUG_LIEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_GAMME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_PRIX:      [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_LIVRAISON: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )

    # Conversation : ajout profil
    ajout_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout", ajout_start)],
        states={
            ADMIN_WAIT_DEP:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_dep)],
            ADMIN_WAIT_NOM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_nom)],
            ADMIN_WAIT_LIEN:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_lien)],
            ADMIN_WAIT_CERTIFIED: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_certified)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )

    # Conversation : suppression profil
    suppr_conv = ConversationHandler(
        entry_points=[CommandHandler("suppr", suppr_start)],
        states={
            ADMIN_SUPPR_NOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, suppr_nom)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )

    app.add_handler(code_conv)
    app.add_handler(certif_conv)
    app.add_handler(ajout_conv)
    app.add_handler(suppr_conv)
    # Conversations SK-AM
    ajout_skam_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout_skam", ajout_skam_start)],
        states={
            SKAM_WAIT_NOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_skam_nom)],
            SKAM_WAIT_LIEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_skam_lien)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )
    # Conversations Promos
    ajout_promo_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout_promo", ajout_promo_start)],
        states={
            PROMO_WAIT_NOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_nom)],
            PROMO_WAIT_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_emoji)],
            PROMO_WAIT_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_code)],
            PROMO_WAIT_REDUC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_reduc)],
            PROMO_WAIT_LIEN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_lien)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )
    app.add_handler(ajout_skam_conv)
    app.add_handler(ajout_promo_conv)

    app.add_handler(CommandHandler("menu",       menu_cmd))
    app.add_handler(CommandHandler("admin",      admin_panel))
    app.add_handler(CommandHandler("liste_dep",  liste_dep))
    app.add_handler(CommandHandler("stats",      stats))
    app.add_handler(CommandHandler("get_my_id",  get_my_id))
    app.add_handler(CommandHandler("suppr_skam",  suppr_skam))
    app.add_handler(CommandHandler("suppr_promo", suppr_promo))
    app.add_handler(CallbackQueryHandler(geo_start_cb,      pattern="^geo_start$"))
    app.add_handler(CallbackQueryHandler(show_departements, pattern="^region_"))
    app.add_handler(CallbackQueryHandler(show_profils,      pattern="^dep_"))
    app.add_handler(CallbackQueryHandler(show_profil_detail,pattern="^profil_"))
    app.add_handler(CallbackQueryHandler(handle_menu_cb,    pattern="^(menu_|home|promo_)"))

    print("🤖 La Note Verte — Bot lancé !")
    app.run_polling()

if __name__ == "__main__":
    main()
