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
PROFILS      = load_json("profils.json")
CONFIG       = load_json("config.json")
SKAM         = load_json("skam.json")
PROMOS       = load_json("promos.json")

SECRET_CODE   = "STONNABIS"
ADMIN_CODE    = "Luphima6274"
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

UNLOCKED_USERS = set()
ADMIN_USERS    = set()

# Etats conversation
(
    WAIT_CODE,
    CERTIF_1, CERTIF_2, CERTIF_3, CERTIF_4, CERTIF_5, CERTIF_6,
    AJOUT_DEP, AJOUT_NOM, AJOUT_LIEN, AJOUT_CERTIFIED,
    SUPPR_NOM,
    SKAM_NOM, SKAM_LIEN,
    PROMO_NOM, PROMO_EMOJI, PROMO_CODE, PROMO_REDUC, PROMO_LIEN,
    ADMIN_WAIT,
) = range(20)

CERTIF_FILTRE_TYPE, CERTIF_FILTRE_DEP = 20, 21

CERTIF_QUESTIONS = [
    ("pseudo",    "👤 Ton *pseudo Telegram* ?",       "@ton_pseudo"),
    ("plug_nom",  "🏷️ *Nom du plug* a certifier ?",   "Nom ou pseudo"),
    ("plug_lien", "🔗 *Lien du plug ou menu* ?",      "t.me/... ou lien"),
    ("gamme",     "🌿 *Gamme de reference* ?",        "CBD fleur, resine..."),
    ("prix_min",  "💶 *Prix minimum* pratique ?",     "Ex : a partir de 10 euros"),
    ("livraison", "📦 *Livraison ou envoi postal ?*", "Livraison / Postal / Les deux"),
]

ADMIN_HELP = (
    "⚙️ *Panel Admin*\n\n"
    "*Profils :*\n"
    "➕ /ajout\n"
    "🗑️ /suppr\n"
    "📋 /liste_dep XX\n\n"
    "*SK-AM :*\n"
    "➕ /ajout_skam\n"
    "🗑️ /suppr_skam\n\n"
    "*Promos :*\n"
    "➕ /ajout_promo\n"
    "🗑️ /suppr_promo\n\n"
    "📊 /stats"
)

async def notify_admin(context, text):
    if ADMIN_CHAT_ID:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Liste Certified", callback_data="menu_certified"),
         InlineKeyboardButton("📞 Contact",         url="https://t.me/stoneboy_420")],
        [InlineKeyboardButton("📋 Liste SK-AM",     callback_data="menu_skam"),
         InlineKeyboardButton("🌐 Nos Reseaux",     callback_data="menu_reseaux")],
        [InlineKeyboardButton("🎁 Concours",        callback_data="menu_concours"),
         InlineKeyboardButton("🏷️ Code Promo",      callback_data="menu_promo")],
        [InlineKeyboardButton("📍 Trouver un profil pres de moi", callback_data="geo_start")],
        [InlineKeyboardButton("🏅 Se faire certifier / Certifier son plug", callback_data="certif_start")],
    ]
    text = f"*{CONFIG['nom_bot']}*\n\n{CONFIG['description']}\n\nChoisis une option :"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in UNLOCKED_USERS or uid in ADMIN_USERS:
        await show_menu(update, context)
        return ConversationHandler.END
    await update.message.reply_text(
        "🍀 *La Note Verte*\n\n"
        "👋 Salut !\n\n"
        "Ici on certifie les meilleurs plugs de France, testes et approuves par nos equipes. "
        "Tu trouveras forcement ton plug prefere 😎\n\n"
        "Si il n'y est pas, hesite pas a contacter nos equipes.\n\n"
        "🔐 Entre ton code d'acces :",
        parse_mode="Markdown"
    )
    return WAIT_CODE

async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    code = update.message.text.strip()
    if code == ADMIN_CODE:
        ADMIN_USERS.add(uid)
        UNLOCKED_USERS.add(uid)
        await update.message.reply_text("✅ Code admin accepte !")
        await show_menu(update, context)
        return ConversationHandler.END
    elif code.upper() == SECRET_CODE:
        UNLOCKED_USERS.add(uid)
        await update.message.reply_text("✅ Acces accorde ! Bienvenue 🍀")
        await show_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Code incorrect. Reessaie :")
        return WAIT_CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Annule. Tape /menu pour revenir.")
    return ConversationHandler.END

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in UNLOCKED_USERS and uid not in ADMIN_USERS:
        await update.message.reply_text("🔐 Tape /start pour acceder au bot.")
        return
    await show_menu(update, context)

# ── /admin ─────────────────────────────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_USERS:
        await update.message.reply_text(ADMIN_HELP, parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text("🔑 Entre le code admin :")
    return ADMIN_WAIT

async def admin_code_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    code = update.message.text.strip()
    if code == ADMIN_CODE:
        ADMIN_USERS.add(uid)
        UNLOCKED_USERS.add(uid)
        await update.message.reply_text("✅ Acces admin accorde !\n\n" + ADMIN_HELP, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Code incorrect.")
    return ConversationHandler.END

# ── Certification ──────────────────────────────────────────────────────────────
async def certif_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if uid not in UNLOCKED_USERS and uid not in ADMIN_USERS:
        await query.edit_message_text("🔐 Tape /start pour acceder au bot.")
        return ConversationHandler.END
    context.user_data["certif"] = {}
    context.user_data["certif_step"] = 0
    _, q, ex = CERTIF_QUESTIONS[0]
    await query.edit_message_text(
        f"🏅 *Demande de certification* - Etape 1/6\n\n{q}\n\n(ex : {ex})\n\n(Tape /annuler pour quitter)",
        parse_mode="Markdown"
    )
    return CERTIF_1

async def certif_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("certif_step", 0)
    key  = CERTIF_QUESTIONS[step][0]
    context.user_data["certif"][key] = update.message.text
    next_step = step + 1
    context.user_data["certif_step"] = next_step
    if next_step < len(CERTIF_QUESTIONS):
        _, q, ex = CERTIF_QUESTIONS[next_step]
        await update.message.reply_text(
            f"*Etape {next_step+1}/6 :*\n\n{q}\n\n(ex : {ex})",
            parse_mode="Markdown"
        )
        return CERTIF_1 + next_step
    data  = context.user_data["certif"]
    user  = update.effective_user
    uname = f"@{user.username}" if user.username else f"ID:{user.id}"
    recap = (
        "✅ *Demande envoyee !*\n\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 Pseudo : {data.get('pseudo','—')}\n"
        f"🏷️ Plug : {data.get('plug_nom','—')}\n"
        f"🔗 Lien : {data.get('plug_lien','—')}\n"
        f"🌿 Gamme : {data.get('gamme','—')}\n"
        f"💶 Prix min : {data.get('prix_min','—')}\n"
        f"📦 Livraison : {data.get('livraison','—')}\n"
        "━━━━━━━━━━━━━━━━\n"
        "Notre equipe te recontactera rapidement 🍀"
    )
    await update.message.reply_text(
        recap,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]),
        parse_mode="Markdown"
    )
    await notify_admin(context,
        "🏅 *Nouvelle demande de certification !*\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 Pseudo : {data.get('pseudo','—')}\n"
        f"🏷️ Plug : {data.get('plug_nom','—')}\n"
        f"🔗 Lien : {data.get('plug_lien','—')}\n"
        f"🌿 Gamme : {data.get('gamme','—')}\n"
        f"💶 Prix min : {data.get('prix_min','—')}\n"
        f"📦 Livraison : {data.get('livraison','—')}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📩 Envoye par : {uname}"
    )
    context.user_data.pop("certif", None)
    context.user_data.pop("certif_step", None)
    return ConversationHandler.END

# ── Admin Profils ──────────────────────────────────────────────────────────────
async def ajout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return ConversationHandler.END
    await update.message.reply_text("➕ Numero du departement ? (ex: 75)")
    return AJOUT_DEP

async def ajout_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dep"] = update.message.text.strip()
    await update.message.reply_text("👤 Nom du profil ?")
    return AJOUT_NOM

async def ajout_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nom"] = update.message.text.strip()
    await update.message.reply_text("🔗 Lien ? (ex: t.me/pseudo ou - pour passer)")
    return AJOUT_LIEN

async def ajout_lien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["lien"] = "" if val == "-" else val
    await update.message.reply_text("✅ Certified ? (oui / non)")
    return AJOUT_CERTIFIED

async def ajout_certified(update: Update, context: ContextTypes.DEFAULT_TYPE):
    certified = update.message.text.strip().lower() in ["oui", "o", "yes"]
    dep = context.user_data["dep"]
    profil = {"nom": context.user_data["nom"], "certified": certified, "contact": context.user_data["lien"]}
    PROFILS.setdefault(dep, []).append(profil)
    save_json("profils.json", PROFILS)
    badge = "✅ Certified" if certified else "Non certified"
    await update.message.reply_text(f"✅ *{profil['nom']}* ajoute dans le {dep} — {badge}", parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def suppr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return ConversationHandler.END
    await update.message.reply_text("🗑️ Nom exact du profil a supprimer ?")
    return SUPPR_NOM

async def suppr_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom = update.message.text.strip()
    for dep, ps in PROFILS.items():
        for i, p in enumerate(ps):
            if p["nom"].lower() == nom.lower():
                ps.pop(i)
                save_json("profils.json", PROFILS)
                await update.message.reply_text(f"✅ *{nom}* supprime.", parse_mode="Markdown")
                return ConversationHandler.END
    await update.message.reply_text(f"😕 *{nom}* introuvable.", parse_mode="Markdown")
    return ConversationHandler.END

async def liste_dep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage : /liste_dep 75")
        return
    dep = args[0].strip()
    ps  = PROFILS.get(dep, [])
    if not ps:
        await update.message.reply_text(f"Aucun profil dans le {dep}.")
        return
    lines = [f"📋 *Profils {dep}* ({len(ps)}) :\n"]
    for i, p in enumerate(ps):
        badge = "✅" if p.get("certified") else "○"
        lines.append(f"{badge} *{i+1}. {p['nom']}*\n   🔗 {p.get('contact','—')}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── Admin SK-AM ────────────────────────────────────────────────────────────────
async def ajout_skam_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return ConversationHandler.END
    await update.message.reply_text("📋 Nom du membre SK-AM ?")
    return SKAM_NOM

async def ajout_skam_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["skam_nom"] = update.message.text.strip()
    await update.message.reply_text("🔗 Lien Telegram ? (ex: https://t.me/pseudo)")
    return SKAM_LIEN

async def ajout_skam_lien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SKAM.append({"nom": context.user_data["skam_nom"], "lien": update.message.text.strip()})
    save_json("skam.json", SKAM)
    await update.message.reply_text(f"✅ *{context.user_data['skam_nom']}* ajoute a SK-AM !", parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def suppr_skam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return
    args = context.args
    if not args:
        liste = "\n".join([f"{i+1}. {m['nom']}" for i, m in enumerate(SKAM)])
        await update.message.reply_text(f"Liste SK-AM :\n\n{liste or 'Vide'}\n\nUsage : /suppr_skam nom exact")
        return
    nom = " ".join(args).strip()
    idx = next((i for i, m in enumerate(SKAM) if m["nom"].lower() == nom.lower()), None)
    if idx is None:
        await update.message.reply_text(f"😕 *{nom}* introuvable.", parse_mode="Markdown")
        return
    SKAM.pop(idx)
    save_json("skam.json", SKAM)
    await update.message.reply_text(f"✅ *{nom}* supprime de SK-AM.", parse_mode="Markdown")

# ── Admin Promos ───────────────────────────────────────────────────────────────
async def ajout_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return ConversationHandler.END
    await update.message.reply_text("🏷️ Nom du commercant ?")
    return PROMO_NOM

async def ajout_promo_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_nom"] = update.message.text.strip()
    await update.message.reply_text("Emoji ? (ex: 🛍️ ou - pour defaut 🏪)")
    return PROMO_EMOJI

async def ajout_promo_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["promo_emoji"] = "🏪" if val == "-" else val
    await update.message.reply_text("Code promo ?")
    return PROMO_CODE

async def ajout_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_code"] = update.message.text.strip()
    await update.message.reply_text("Description reduction ? (ex: -15% sur tout)")
    return PROMO_REDUC

async def ajout_promo_reduc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_reduc"] = update.message.text.strip()
    await update.message.reply_text("🔗 Lien du site ? (ex: https://site.fr)")
    return PROMO_LIEN

async def ajout_promo_lien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    PROMOS.append({
        "nom":       context.user_data["promo_nom"],
        "emoji":     context.user_data["promo_emoji"],
        "code":      context.user_data["promo_code"],
        "reduction": context.user_data["promo_reduc"],
        "lien":      update.message.text.strip(),
    })
    save_json("promos.json", PROMOS)
    await update.message.reply_text(f"✅ Partenaire *{context.user_data['promo_nom']}* ajoute !", parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def suppr_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return
    args = context.args
    if not args:
        liste = "\n".join([f"{i+1}. {p['emoji']} {p['nom']}" for i, p in enumerate(PROMOS)])
        await update.message.reply_text(f"Partenaires :\n\n{liste or 'Vide'}\n\nUsage : /suppr_promo nom exact")
        return
    nom = " ".join(args).strip()
    idx = next((i for i, p in enumerate(PROMOS) if p["nom"].lower() == nom.lower()), None)
    if idx is None:
        await update.message.reply_text(f"😕 *{nom}* introuvable.", parse_mode="Markdown")
        return
    PROMOS.pop(idx)
    save_json("promos.json", PROMOS)
    await update.message.reply_text(f"✅ *{nom}* supprime.", parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USERS:
        return
    total     = sum(len(v) for v in PROFILS.values())
    certified = sum(1 for v in PROFILS.values() for p in v if p.get("certified"))
    await update.message.reply_text(
        f"📊 *Stats La Note Verte*\n\n"
        f"👥 Profils : *{total}*\n"
        f"✅ Certified : *{certified}*\n"
        f"📋 Membres SK-AM : *{len(SKAM)}*\n"
        f"🏷️ Partenaires : *{len(PROMOS)}*\n"
        f"🔓 Connectes : *{len(UNLOCKED_USERS)}*",
        parse_mode="Markdown"
    )

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔑 Ton Chat ID : `{update.effective_user.id}`", parse_mode="Markdown")

# ── Geo ────────────────────────────────────────────────────────────────────────
async def geo_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    regions = {}
    for n, d in DEPARTEMENTS.items():
        regions.setdefault(d["region"], []).append(n)
    keyboard = [[InlineKeyboardButton(f"📌 {r}", callback_data=f"region_{r}")] for r in sorted(regions)]
    keyboard.append([InlineKeyboardButton("🏠 Retour", callback_data="home")])
    await query.edit_message_text("🗺️ *Choisis ta region :*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_departements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region = query.data.replace("region_", "")
    deps   = sorted([(n, d["nom"]) for n, d in DEPARTEMENTS.items() if d["region"] == region])
    keyboard = [[InlineKeyboardButton(f"{n} - {nom}", callback_data=f"dep_{n}")] for n, nom in deps]
    keyboard.append([InlineKeyboardButton("◀️ Regions", callback_data="geo_start")])
    await query.edit_message_text(f"📍 *{region}*\nChoisis ton departement :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profils(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    dep_num = query.data.replace("dep_", "")
    dep_nom = DEPARTEMENTS.get(dep_num, {}).get("nom", dep_num)
    region  = DEPARTEMENTS.get(dep_num, {}).get("region", "")
    ps      = PROFILS.get(dep_num, [])
    if not ps:
        keyboard = [[InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")]]
        await query.edit_message_text(f"😕 Aucun profil pour *{dep_nom}* ({dep_num}).\n\nHesite pas a contacter nos equipes ! 🍀", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    keyboard = [[InlineKeyboardButton(f"{'✅ ' if p.get('certified') else ''}{p['nom']}", callback_data=f"profil_{dep_num}_{i}")] for i, p in enumerate(ps)]
    keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")])
    await query.edit_message_text(f"👥 *{dep_nom} ({dep_num})*\n{len(ps)} profil(s)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profil_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, dep_num, idx_str = query.data.split("_", 2)
    p = PROFILS[dep_num][int(idx_str)]
    lines = []
    if p.get("certified"): lines.append("✅ *CERTIFIED*")
    lines.append(f"👤 *{p['nom']}*")
    if p.get("secteur"):   lines.append(f"📍 {p['secteur']}")
    else:                  lines.append(f"📍 Departement {dep_num}")
    keyboard = []
    if p.get("contact"):
        keyboard.append([InlineKeyboardButton("🔗 Acceder au profil", url=p["contact"])])
    keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data=f"dep_{dep_num}")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ── Pages menu ─────────────────────────────────────────────────────────────────
async def handle_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    action = query.data
    back   = [[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]

    static = {
        "menu_certified": None,
        "menu_contact":   CONFIG.get("texte_contact", ""),

        "menu_concours":   None,
    }

    if action in static and static[action] is not None:
        await query.edit_message_text(static[action], reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")

    elif action == "menu_certified":
        keyboard = [
            [InlineKeyboardButton("🚗 Livraison / Meet Up", callback_data="certif_f_meetup")],
            [InlineKeyboardButton("📦 Envoi Postal",        callback_data="certif_f_postale")],
            [InlineKeyboardButton("🏠 Accueil", callback_data="home")],
        ]
        await query.edit_message_text(
            "✅ *Liste Certified*\n\nNos profils testes et approuves par nos equipes 💯\n\nChoisis ton mode de livraison :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action in ("certif_f_meetup", "certif_f_postale"):
        filtre = "meetup" if action == "certif_f_meetup" else "postale"
        label  = "🚗 Livraison / Meet Up" if filtre == "meetup" else "📦 Envoi Postal"
        certified_list = [(dep, i, p) for dep, ps in PROFILS.items() for i, p in enumerate(ps) if p.get("certified") and p.get("livraison") == filtre]
        if not certified_list:
            keyboard = [
                [InlineKeyboardButton("◀️ Retour", callback_data="menu_certified")],
                [InlineKeyboardButton("🏠 Accueil", callback_data="home")],
            ]
            await query.edit_message_text(f"✅ *{label}*\n\nAucun profil disponible pour ce mode.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
        keyboard = []
        for dep, i, p in certified_list:
            secteur = p.get("secteur", f"Dep. {dep}")
            keyboard.append([InlineKeyboardButton(f"✅ {p['nom']} — {secteur}", callback_data=f"profil_{dep}_{i}")])
        keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data="menu_certified")])
        keyboard.append([InlineKeyboardButton("🏠 Accueil", callback_data="home")])
        await query.edit_message_text(
            f"✅ *{label}*\n\n{len(certified_list)} profil(s) disponible(s) :",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action == "menu_concours":
        keyboard = [
            [InlineKeyboardButton("📸 Abonne-toi sur Instagram", url="https://www.instagram.com/stoneboy_420?igsh=N3JlZ3hwenJ1b3Q2&utm_source=qr")],
            [InlineKeyboardButton("🏠 Accueil", callback_data="home")],
        ]
        await query.edit_message_text(
            "⚙️⏳⌛️\n\n*Concours en cours de preparation...*\n\nAbonne-toi pour ne rien louper !",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action == "menu_reseaux":
        keyboard = [
            [InlineKeyboardButton("📸 Instagram", url="https://www.instagram.com/stoneboy_420?igsh=N3JlZ3hwenJ1b3Q2&utm_source=qr")],
            [InlineKeyboardButton("💬 Telegram",  url="https://t.me/stoneboy_420")],
            [InlineKeyboardButton("🔒 Signal",    url="https://signal.me/#eu/cURmi5ud2CX6zMtp-ho4ORADyPglm45d6H5F13l7Su627Zip-_BJ7J2GD23_coWj")],
            [InlineKeyboardButton("🏠 Accueil", callback_data="home")],
        ]
        await query.edit_message_text("🌐 *Nos Reseaux*\n\nChoisis ta plateforme :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "menu_skam":
        if not SKAM:
            await query.edit_message_text("📋 *Liste SK-AM*\n\nAucun membre pour le moment.", reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(m["nom"], url=m["lien"])] for m in SKAM]
        keyboard.append([InlineKeyboardButton("🏠 Accueil", callback_data="home")])
        await query.edit_message_text("📋 *Liste SK-AM*\n\nClique sur le compte SK-AM et signal le :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "menu_promo":
        if not PROMOS:
            await query.edit_message_text("🏷️ *Codes Promo*\n\nAucun partenaire pour le moment.", reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(f"{p['emoji']} {p['nom']}", callback_data=f"promo_{i}")] for i, p in enumerate(PROMOS)]
        keyboard.append([InlineKeyboardButton("🏠 Accueil", callback_data="home")])
        await query.edit_message_text("🏷️ *Codes Promo - Nos Partenaires*\n\nChoisis un partenaire :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action.startswith("promo_"):
        idx = int(action.replace("promo_", ""))
        p   = PROMOS[idx]
        keyboard = [
            [InlineKeyboardButton("📩 Contacter sur Telegram", url=p["lien"])],
            [InlineKeyboardButton("◀️ Partenaires", callback_data="menu_promo")],
        ]
        text = f"{p['emoji']} *{p['nom']}*\n\n{p['reduction']}"
        if p.get("code"):
            text += f"\n\n🏷️ Code promo :\n`{p['code']}`\n\n(Appuie longuement pour copier)"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action == "home":
        await show_menu(update, context)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN manquant !")

    app = Application.builder().token(TOKEN).build()

    code_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_code)]},
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={ADMIN_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_code_check)]},
        fallbacks=[CommandHandler("annuler", cancel)],
        allow_reentry=True,
    )
    certif_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(certif_start, pattern="^certif_start$")],
        states={
            CERTIF_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_4: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_5: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
            CERTIF_6: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_handler)],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
        per_message=False,
        allow_reentry=True,
    )
    ajout_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout", ajout_start)],
        states={
            AJOUT_DEP:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_dep)],
            AJOUT_NOM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_nom)],
            AJOUT_LIEN:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_lien)],
            AJOUT_CERTIFIED: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_certified)],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
        allow_reentry=True,
    )
    suppr_conv = ConversationHandler(
        entry_points=[CommandHandler("suppr", suppr_start)],
        states={SUPPR_NOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, suppr_nom)]},
        fallbacks=[CommandHandler("annuler", cancel)],
        allow_reentry=True,
    )
    ajout_skam_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout_skam", ajout_skam_start)],
        states={
            SKAM_NOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_skam_nom)],
            SKAM_LIEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_skam_lien)],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
        allow_reentry=True,
    )
    ajout_promo_conv = ConversationHandler(
        entry_points=[CommandHandler("ajout_promo", ajout_promo_start)],
        states={
            PROMO_NOM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_nom)],
            PROMO_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_emoji)],
            PROMO_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_code)],
            PROMO_REDUC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_reduc)],
            PROMO_LIEN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ajout_promo_lien)],
        },
        fallbacks=[CommandHandler("annuler", cancel)],
        allow_reentry=True,
    )

    app.add_handler(code_conv)
    app.add_handler(admin_conv)
    app.add_handler(certif_conv)
    app.add_handler(ajout_conv)
    app.add_handler(suppr_conv)
    app.add_handler(ajout_skam_conv)
    app.add_handler(ajout_promo_conv)
    app.add_handler(CommandHandler("menu",        menu_cmd))
    app.add_handler(CommandHandler("liste_dep",   liste_dep))
    app.add_handler(CommandHandler("stats",       stats))
    app.add_handler(CommandHandler("get_my_id",   get_my_id))
    app.add_handler(CommandHandler("suppr_skam",  suppr_skam))
    app.add_handler(CommandHandler("suppr_promo", suppr_promo))
    app.add_handler(CallbackQueryHandler(geo_start_cb,       pattern="^geo_start$"))
    app.add_handler(CallbackQueryHandler(show_departements,  pattern="^region_"))
    app.add_handler(CallbackQueryHandler(show_profils,       pattern="^dep_"))
    app.add_handler(CallbackQueryHandler(show_profil_detail, pattern="^profil_"))
    app.add_handler(CallbackQueryHandler(handle_menu_cb,     pattern="^(menu_|home|promo_|certif_f_)"))

    print("🤖 La Note Verte - Bot lance !")
    app.run_polling()

if __name__ == "__main__":
    main()
