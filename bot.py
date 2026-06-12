import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "departements.json"), encoding="utf-8") as f:
    DEPARTEMENTS = json.load(f)
with open(os.path.join(BASE_DIR, "profils.json"), encoding="utf-8") as f:
    PROFILS = json.load(f)
with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)

# ── Ton Chat ID — récupéré via /get_my_id ──────────────────────────────────
# Remplace cette valeur après avoir obtenu ton ID avec /get_my_id
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))

# ── Étapes du formulaire de certification ──────────────────────────────────
CERTIF_PSEUDO, CERTIF_PLUG_NOM, CERTIF_PLUG_LIEN, CERTIF_GAMME, CERTIF_PRIX, CERTIF_LIVRAISON = range(6)

CERTIF_QUESTIONS = [
    ("pseudo",     "👤 Quel est ton *pseudo Telegram* ?",                  "@ton_pseudo"),
    ("plug_nom",   "🏷️ Quel est le *nom du plug* à certifier ?",           "Nom ou pseudo du plug"),
    ("plug_lien",  "🔗 *Lien du plug ou du menu* (Telegram, site…) ?",     "t.me/... ou lien menu"),
    ("gamme",      "🌿 Quelle est sa *gamme de référence* ?",              "Ex : CBD fleur, résine, huile…"),
    ("prix_min",   "💶 Quel est le *prix minimum* pratiqué ?",             "Ex : à partir de 10€"),
    ("livraison",  "📦 *Livraison ou envoi postal ?*",                     "Livraison / Postal / Les deux"),
]

# ── Helper : envoyer notif admin ───────────────────────────────────────────
async def notify_admin(context, data: dict, user):
    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID non configuré — notification ignorée")
        return
    username = f"@{user.username}" if user.username else f"ID:{user.id}"
    msg = (
        "🏅 *Nouvelle demande de certification !*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Pseudo :* {data.get('pseudo', '—')}\n"
        f"🏷️ *Plug :* {data.get('plug_nom', '—')}\n"
        f"🔗 *Lien :* {data.get('plug_lien', '—')}\n"
        f"🌿 *Gamme :* {data.get('gamme', '—')}\n"
        f"💶 *Prix min :* {data.get('prix_min', '—')}\n"
        f"📦 *Livraison :* {data.get('livraison', '—')}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📩 *Envoyé par :* {username}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode="Markdown")

# ── /get_my_id : récupérer son Chat ID ────────────────────────────────────
async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔑 Ton Chat ID est : `{update.effective_user.id}`\n\n"
        "Copie ce numéro et mets-le dans la variable `ADMIN_CHAT_ID` du bot.",
        parse_mode="Markdown"
    )

# ── Menu principal ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Liste Certified", callback_data="menu_certified"),
         InlineKeyboardButton("📞 Contact", callback_data="menu_contact")],
        [InlineKeyboardButton("📋 Liste SK-AM", callback_data="menu_skam"),
         InlineKeyboardButton("🌐 Nos Réseaux", callback_data="menu_reseaux")],
        [InlineKeyboardButton("🎁 Concours", callback_data="menu_concours"),
         InlineKeyboardButton("🏷️ Code Promo", callback_data="menu_promo")],
        [InlineKeyboardButton("📍 Trouver un profil près de moi", callback_data="geo_start")],
        [InlineKeyboardButton("🏅 Se faire certifier / Certifier son plug", callback_data="certif_start")],
    ]
    text = (
        f"*{CONFIG['nom_bot']}*\n\n"
        f"{CONFIG['description']}\n\n"
        "Choisis une option :"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ── Démarrer le formulaire de certification ────────────────────────────────
async def certif_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["certif"] = {}
    context.user_data["certif_step"] = 0
    key, question, exemple = CERTIF_QUESTIONS[0]
    await query.edit_message_text(
        "🏅 *Demande de certification*\n\n"
        "_Réponds aux questions suivantes. Étape 1/6 :_\n\n"
        f"{question}\n\n"
        f"_(ex : {exemple})_",
        parse_mode="Markdown"
    )
    return CERTIF_PSEUDO

# ── Gérer chaque réponse du formulaire ────────────────────────────────────
async def certif_step_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("certif_step", 0)
    key = CERTIF_QUESTIONS[step][0]
    context.user_data["certif"][key] = update.message.text
    context.user_data["certif_step"] = step + 1
    next_step = step + 1

    if next_step < len(CERTIF_QUESTIONS):
        _, question, exemple = CERTIF_QUESTIONS[next_step]
        await update.message.reply_text(
            f"*Étape {next_step + 1}/6 :*\n\n{question}\n\n_(ex : {exemple})_",
            parse_mode="Markdown"
        )
        return next_step
    else:
        # Formulaire terminé
        data = context.user_data["certif"]
        recap = (
            "✅ *Demande envoyée !*\n\n"
            "Voici le récap de ta demande :\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Pseudo :* {data.get('pseudo','—')}\n"
            f"🏷️ *Plug :* {data.get('plug_nom','—')}\n"
            f"🔗 *Lien :* {data.get('plug_lien','—')}\n"
            f"🌿 *Gamme :* {data.get('gamme','—')}\n"
            f"💶 *Prix min :* {data.get('prix_min','—')}\n"
            f"📦 *Livraison :* {data.get('livraison','—')}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Notre équipe va examiner ta demande et te recontacter rapidement. Merci ! 🍀"
        )
        keyboard = [[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]
        await update.message.reply_text(recap, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        # ── Notification à @stoneboy_420 ──
        await notify_admin(context, data, update.effective_user)

        context.user_data.pop("certif", None)
        context.user_data.pop("certif_step", None)
        return ConversationHandler.END

async def certif_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("certif", None)
    context.user_data.pop("certif_step", None)
    await update.message.reply_text("❌ Demande annulée.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]))
    return ConversationHandler.END

# ── Géolocalisation ────────────────────────────────────────────────────────
async def geo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    regions = {}
    for dep_num, dep_data in DEPARTEMENTS.items():
        region = dep_data["region"]
        if region not in regions:
            regions[region] = []
        regions[region].append((dep_num, dep_data["nom"]))
    keyboard = [[InlineKeyboardButton(f"📌 {r}", callback_data=f"region_{r}")] for r in sorted(regions.keys())]
    keyboard.append([InlineKeyboardButton("🏠 Retour", callback_data="home")])
    await query.edit_message_text("🗺️ *Choisis ta région :*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_departements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_name = query.data.replace("region_", "")
    deps = [(num, data["nom"]) for num, data in DEPARTEMENTS.items() if data["region"] == region_name]
    deps.sort(key=lambda x: x[0])
    keyboard = [[InlineKeyboardButton(f"{n} – {nom}", callback_data=f"dep_{n}")] for n, nom in deps]
    keyboard.append([InlineKeyboardButton("◀️ Régions", callback_data="geo_start")])
    await query.edit_message_text(f"📍 *{region_name}* – Choisis ton département :", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profils(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dep_num = query.data.replace("dep_", "")
    dep_nom = DEPARTEMENTS.get(dep_num, {}).get("nom", dep_num)
    region = DEPARTEMENTS.get(dep_num, {}).get("region", "")
    profils_dep = PROFILS.get(dep_num, [])
    if not profils_dep:
        keyboard = [[InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")]]
        await query.edit_message_text(f"😕 Aucun profil pour *{dep_nom}* ({dep_num}) pour le moment.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    keyboard = [[InlineKeyboardButton(f"{'✅ ' if p.get('certified') else ''}{p['nom']}", callback_data=f"profil_{dep_num}_{i}")] for i, p in enumerate(profils_dep)]
    keyboard.append([InlineKeyboardButton("◀️ Retour", callback_data=f"region_{region}")])
    await query.edit_message_text(f"👥 *Profils – {dep_nom} ({dep_num})* :\n{len(profils_dep)} profil(s)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_profil_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, dep_num, idx_str = query.data.split("_", 2)
    profil = PROFILS[dep_num][int(idx_str)]
    lines = [f"{'✅ *CERTIFIED*' + chr(10) if profil.get('certified') else ''}👤 *{profil['nom']}*", f"📍 {profil.get('ville','N/A')} ({dep_num})"]
    if profil.get("description"): lines.append(f"\n_{profil['description']}_")
    if profil.get("contact"): lines.append(f"\n📬 {profil['contact']}")
    keyboard = [[InlineKeyboardButton("◀️ Retour", callback_data=f"dep_{dep_num}")]]
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ── Pages statiques ────────────────────────────────────────────────────────
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    back = [[InlineKeyboardButton("🏠 Accueil", callback_data="home")]]
    pages = {
        "menu_certified": CONFIG.get("texte_certified",""),
        "menu_contact":   CONFIG.get("texte_contact",""),
        "menu_skam":      CONFIG.get("texte_skam",""),
        "menu_reseaux":   CONFIG.get("texte_reseaux",""),
        "menu_concours":  "⚙️⏳⌛️\n\n*Concours en cours de préparation…*\n\nReviens bientôt !",
        "menu_promo":     CONFIG.get("texte_promo",""),
    }
    if action in pages:
        await query.edit_message_text(pages[action], reply_markup=InlineKeyboardMarkup(back), parse_mode="Markdown")
    elif action in ("home", "certif_start"):
        if action == "certif_start":
            await certif_start(update, context)
        else:
            await start(update, context)

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN manquant !")

    app = Application.builder().token(TOKEN).build()

    # Conversation handler pour la certification
    certif_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(certif_start, pattern="^certif_start$")],
        states={
            CERTIF_PSEUDO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
            CERTIF_PLUG_NOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
            CERTIF_PLUG_LIEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
            CERTIF_GAMME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
            CERTIF_PRIX:      [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
            CERTIF_LIVRAISON: [MessageHandler(filters.TEXT & ~filters.COMMAND, certif_step_handler)],
        },
        fallbacks=[CommandHandler("annuler", certif_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get_my_id", get_my_id))
    app.add_handler(certif_conv)
    app.add_handler(CallbackQueryHandler(geo_start,          pattern="^geo_start$"))
    app.add_handler(CallbackQueryHandler(show_departements,  pattern="^region_"))
    app.add_handler(CallbackQueryHandler(show_profils,       pattern="^dep_"))
    app.add_handler(CallbackQueryHandler(show_profil_detail, pattern="^profil_"))
    app.add_handler(CallbackQueryHandler(handle_menu,        pattern="^(menu_|home|certif_start)"))

    print("🤖 Bot lancé — notifications actives sur ADMIN_CHAT_ID")
    app.run_polling()

if __name__ == "__main__":
    main()
