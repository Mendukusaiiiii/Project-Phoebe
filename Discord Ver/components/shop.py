import asyncio
import json
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import discord
from discord import app_commands

DATA_DIR = "data"
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")
ROLES_KEY = "_roles" 
EMBED_COLOR = 0xFFBF00 
INVENTORY_FOOTER = "Manage your roles below."

CUSTOM_KEY = "_custom_roles"
CUSTOM_ROLE_EDIT_COST = 0           
CUSTOM_ROLE_NAME_MAX = 32
DEFAULT_CUSTOM_COLOR = 0xFFBF00

SHOP_ITEMS_FILE = os.path.join(DATA_DIR, "shop_items.json")
ARCHIVE_FILE = os.path.join(DATA_DIR, "archived_items.json") 

DEFAULT_SHOP_ITEMS = []


CATEGORIES = {
    "custom": ("Custom Role", "🎭"),
    "general": ("General Items", "🛍️"),
    "limited": ("Limited Items", "⏳"),
}
DEFAULT_CATEGORY = "general"  
STOCK_KEY = "_stock_sold"  

CUSTOM_ROLE_ITEM = {
    "id": "custom_role",
    "name": "Custom Role",
    "emoji": "🎨",
    "price": 1_000,
    "type": "custom_role",
    "category": "custom",
    "description": "Design your own role.",
}


def _read_json_list(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path) 


def _normalize_item(raw: dict) -> dict:
    item = dict(raw)
    color = item.get("color", DEFAULT_CUSTOM_COLOR)
    if isinstance(color, str):
        color = int(color.strip().lstrip("#"), 16)
    item["color"] = color
    item.setdefault("type", "title")
    item.setdefault("title", item["name"])
    if item.get("category") not in CATEGORIES:
        if item.get("stock") is not None:
            item["category"] = "limited"
        elif item["type"] == "custom_role":
            item["category"] = "custom"
        else:
            item["category"] = "general"
    return item


def load_shop_items() -> list[dict]:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SHOP_ITEMS_FILE):
        _write_json(SHOP_ITEMS_FILE, DEFAULT_SHOP_ITEMS)
    return [_normalize_item(raw) for raw in _read_json_list(SHOP_ITEMS_FILE)]


def load_archived_items(active_ids: set) -> list[dict]:
    """Sold-out items. Not shown in the shop, but owners can still equip them."""
    raw_items = _read_json_list(ARCHIVE_FILE)
    kept = [r for r in raw_items if r.get("id") not in active_ids]
    if len(kept) != len(raw_items) or not os.path.exists(ARCHIVE_FILE):
        _write_json(ARCHIVE_FILE, kept)
    return [_normalize_item(raw) for raw in kept]


SHOP_ITEMS = load_shop_items() + [CUSTOM_ROLE_ITEM]
ARCHIVED_ITEMS = load_archived_items({item["id"] for item in SHOP_ITEMS})
ITEMS_BY_ID = {item["id"]: item for item in SHOP_ITEMS + ARCHIVED_ITEMS}


def _all_items() -> list[dict]:
    return SHOP_ITEMS + ARCHIVED_ITEMS


def _items_in_category(category: str) -> list[dict]:
    return [item for item in SHOP_ITEMS if item["category"] == category]


def load_inventory():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, "w") as f:
            json.dump({}, f, indent=4)
        return {}
    with open(INVENTORY_FILE, "r") as f:
        return json.load(f)


def save_inventory(data):
    _write_json(INVENTORY_FILE, data)


inventory_data = load_inventory()


def _stock_left(item: dict) -> int | None:
    total = item.get("stock")
    if total is None:
        return None
    sold = inventory_data.get(STOCK_KEY, {}).get(item["id"], 0)
    return max(int(total) - sold, 0)


def _change_sold(item_id: str, delta: int):
    sold = inventory_data.setdefault(STOCK_KEY, {})
    sold[item_id] = max(sold.get(item_id, 0) + delta, 0)


def _archive_item(item: dict) -> None:
    if item not in SHOP_ITEMS:
        return
    SHOP_ITEMS.remove(item)
    ARCHIVED_ITEMS.append(item)

    shop_raw = _read_json_list(SHOP_ITEMS_FILE)
    entry = next((r for r in shop_raw if r.get("id") == item["id"]), None)
    if entry is None:
        entry = {k: v for k, v in item.items() if k != "color"}
        entry["color"] = f"#{item['color']:06X}"
    entry = dict(entry)
    entry["archived_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    archived_raw = [r for r in _read_json_list(ARCHIVE_FILE) if r.get("id") != item["id"]]
    archived_raw.append(entry)
    _write_json(ARCHIVE_FILE, archived_raw)
    _write_json(SHOP_ITEMS_FILE, [r for r in shop_raw if r.get("id") != item["id"]])


def _archive_sold_out() -> None:
    for item in list(SHOP_ITEMS):
        if _stock_left(item) == 0:
            _archive_item(item)


_archive_sold_out()  


def _item_status(user: discord.abc.User, item: dict) -> str | None:
    if item["type"] != "title":
        return None
    guild = getattr(user, "guild", None)
    if guild is not None and isinstance(user, discord.Member):
        member = guild.get_member(user.id) or user
        role_id = inventory_data.get(ROLES_KEY, {}).get(str(guild.id), {}).get(item["id"])
        if role_id is not None and any(r.id == role_id for r in member.roles):
            return "equipped"
    if item["title"] in inventory_data.get(str(user.id), {}).get("titles", []):
        return "owned"
    return None


def get_title(user_id: int) -> str | None:
    return inventory_data.get(str(user_id), {}).get("title")


_eco = SimpleNamespace()


def _build_embed(user: discord.abc.User, category: str = DEFAULT_CATEGORY) -> discord.Embed:
    guild = getattr(user, "guild", None)

    cat_name, cat_emoji = CATEGORIES[category]
    embed = discord.Embed(
        title=f"Shop - {cat_emoji} {cat_name}",
        description=(
            f"Your balance: **{_eco.format_currency(_eco.get_balance(user.id))}**\n"
            "Pick an item from the menu below to buy it."
        ),
        color=EMBED_COLOR,
    )
    category_items = _items_in_category(category)[:25]  
    if not category_items:
        embed.add_field(name="Nothing here yet", value="Check back later!", inline=False)
    for item in category_items:
        note = ""
        status_text = {"equipped": " *(equipped)*", "owned": " *(owned)*"}.get(
            _item_status(user, item), ""
        )
        left = _stock_left(item)
        if left is not None:
            if left > 0:
                note += f"\n⏳ **{left}/{item['stock']}** left"
            else:
                note += "\n❌ **Sold out**"
        if item["type"] == "custom_role":
            record = None
            if guild is not None:
                record = inventory_data.get(CUSTOM_KEY, {}).get(str(guild.id), {}).get(str(user.id))
            if record:
                note += (
                    f"\n*You have: **{record['name']}**. Changing the name costs "
                    f"{_eco.format_currency(item['price'])}. Changing the color is free.*"
                )
        embed.add_field(
            name=f"{item['emoji']} {item['name']} - {_eco.format_currency(item['price'])}",
            value=item["description"] + status_text + note,
            inline=False,
        )
    return embed


def _shop_role_ids(guild_id: int) -> dict:
    return inventory_data.setdefault(ROLES_KEY, {}).setdefault(str(guild_id), {})


async def _get_or_create_role(guild: discord.Guild, item: dict) -> discord.Role:
    role_ids = _shop_role_ids(guild.id)
    role = guild.get_role(role_ids.get(item["id"], 0))
    if role is None:
        role = await guild.create_role(
            name=item["title"],
            colour=discord.Colour(item["color"]),
            reason="Shop title purchase",
        )
        role_ids[item["id"]] = role.id
        save_inventory(inventory_data)
    return role


async def _equip_title_role(member: discord.Member, item: dict):
    role = await _get_or_create_role(member.guild, item)
    shop_ids = set(_shop_role_ids(member.guild.id).values())
    others = [r for r in member.roles if r.id in shop_ids and r.id != role.id]
    if others:
        await member.remove_roles(*others, reason="Switched shop title")
    if role not in member.roles:
        await member.add_roles(role, reason="Shop title purchase")


_purchase_locks: dict[int, asyncio.Lock] = {}


async def _purchase(interaction: discord.Interaction, item: dict) -> str:
    lock = _purchase_locks.setdefault(interaction.user.id, asyncio.Lock())
    async with lock:
        return await _purchase_unlocked(interaction, item)


async def _purchase_unlocked(interaction: discord.Interaction, item: dict) -> str:
    user = interaction.user
    user_id = str(user.id)


    if item["type"] == "title":
        guild = interaction.guild
        if guild is None or not isinstance(user, discord.Member):
            return "Titles are roles, so you need to open /shop in a server to buy one."
        if not guild.me.guild_permissions.manage_roles:
            return "I need the **Manage Roles** permission in this server to hand out title roles."

   
        entry = inventory_data.setdefault(user_id, {})
        owned = entry.setdefault("titles", [])
        if item["title"] in owned:
            existing = guild.get_role(_shop_role_ids(guild.id).get(item["id"], 0))
            if existing is not None and existing in user.roles:
                return f"You're already wearing the **{item['title']}** role."
            try:
                await _equip_title_role(user, item)
            except (discord.Forbidden, discord.HTTPException):
                return "I couldn't give you that role. Make sure my role is above the title roles."
            entry["title"] = item["title"]
            save_inventory(inventory_data)
            return f"Equipped your **{item['title']}** role. No charge."

    limited = _stock_left(item) is not None
    if limited and _stock_left(item) <= 0:
        return f"**{item['name']}** is sold out."

    price = item["price"]
    balance = _eco.get_balance(user.id)
    if balance < price:
        return (
            f"You need **{_eco.format_currency(price)}** for **{item['name']}**, "
            f"but you only have **{_eco.format_currency(balance)}**."
        )

    if limited:
        _change_sold(item["id"], +1)

    if item["type"] == "title":
        try:
            await _equip_title_role(user, item)
        except (discord.Forbidden, discord.HTTPException):
            if limited:
                _change_sold(item["id"], -1)
            return (
                "I couldn't create or give that role, and you weren't charged. "
                "Make sure I have **Manage Roles** and my role is high enough."
            )

    _eco.balances_data[user_id] = balance - price
    _eco.save_balances(_eco.balances_data)

    entry = inventory_data.setdefault(user_id, {})
    titles = entry.setdefault("titles", [])
    if item["title"] not in titles:
        titles.append(item["title"])
    entry["title"] = item["title"]
    save_inventory(inventory_data)
    result = f"You're now wearing the **{item['title']}** role."

    last_one = ""
    if limited and _stock_left(item) == 0:
        _archive_item(item)
        last_one = "\nYou got the last one! It's now sold out and archived."

    return (
        f"Bought **{item['name']}** for **{_eco.format_currency(price)}**. {result}\n"
        f"New balance: **{_eco.format_currency(_eco.get_balance(user.id))}**.{last_one}"
    )

def _custom_records(guild_id: int) -> dict:
    return inventory_data.setdefault(CUSTOM_KEY, {}).setdefault(str(guild_id), {})


def _parse_color(text: str) -> int:
    text = text.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        raise ValueError(text)
    return int(text, 16)


async def _apply_custom_role(interaction: discord.Interaction, item: dict,
                             raw_name: str, raw_color: str) -> str:
    user, guild = interaction.user, interaction.guild
    if guild is None or not isinstance(user, discord.Member):
        return "Custom roles live in a server, so open /shop in a server."
    if not guild.me.guild_permissions.manage_roles:
        return "I need the **Manage Roles** permission in this server to make custom roles."

    name = " ".join(raw_name.split()) 
    if not name:
        return "The role name can't be empty."
    if len(name) > CUSTOM_ROLE_NAME_MAX:
        return f"Role names can be at most {CUSTOM_ROLE_NAME_MAX} characters."
    if not _eco.name_allowed(guild.id, name):
        return "That name isn't allowed in this server. Try a different one."

    user_id = str(user.id)
    records = _custom_records(guild.id)
    record = records.get(user_id)
    own_role = guild.get_role(record["role_id"]) if record else None


    taken = {r.name.lower() for r in guild.roles if own_role is None or r.id != own_role.id}
    if name.lower() in taken:
        return f"A role named **{name}** already exists in this server. Pick another name."

    if raw_color.strip():
        try:
            color = _parse_color(raw_color)
        except ValueError:
            return "That isn't a valid hex color. Use something like `#FF8800`."
    else:
        color = record["color"] if record else DEFAULT_CUSTOM_COLOR

    name_changed = record is None or name != record["name"]
    if not name_changed and own_role is not None and own_role in user.roles and color == record["color"]:
        return "Nothing changed, so you weren't charged."

    cost = item["price"] if name_changed else 0
    balance = _eco.get_balance(user.id)
    if balance < cost:
        return (
            f"You need **{_eco.format_currency(cost)}** for that, "
            f"but you only have **{_eco.format_currency(balance)}**."
        )

    created = None
    try:
        if own_role is None:
            own_role = created = await guild.create_role(
                name=name, colour=discord.Colour(color), reason=f"Custom role for {user}"
            )
        else:
            await own_role.edit(name=name, colour=discord.Colour(color), reason=f"Custom role edited by {user}")
        if own_role not in user.roles:
            await user.add_roles(own_role, reason="Custom role")
    except (discord.Forbidden, discord.HTTPException):
        if created is not None:
            try:
                await created.delete(reason="Custom role setup failed")
            except discord.HTTPException:
                pass
        return (
            "I couldn't set up that role, and you weren't charged. "
            "Make sure I have **Manage Roles** and my role is high enough."
        )

    records[user_id] = {"role_id": own_role.id, "name": name, "color": color}
    save_inventory(inventory_data)
    if cost:
        _eco.balances_data[user_id] = balance - cost
        _eco.save_balances(_eco.balances_data)

    verb = "Updated" if record else "Created"
    charge = f" Cost: **{_eco.format_currency(cost)}**." if cost else ""
    return (
        f"{verb} your role {own_role.mention} (color `#{color:06X}`).{charge}\n"
        f"Balance: **{_eco.format_currency(_eco.get_balance(user.id))}**."
    )


class CustomRoleModal(discord.ui.Modal):
    def __init__(self, item: dict, record: dict | None, shop_view: "ShopView"):
        super().__init__(title="Your Custom Role")
        self.item = item
        self.shop_view = shop_view
        self.name_input = discord.ui.TextInput(
            label="Role name",
            placeholder="e.g. Queen of Tea",
            min_length=1,
            max_length=CUSTOM_ROLE_NAME_MAX,
            default=record["name"] if record else None,
        )
        self.color_input = discord.ui.TextInput(
            label="Color (hex code, like #FF8800)",
            placeholder="#FFBF00",
            required=False,
            max_length=7,
            default=f"#{record['color']:06X}" if record else None,
        )
        self.add_item(self.name_input)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await _apply_custom_role(
            interaction, self.item, self.name_input.value, self.color_input.value
        )
        await interaction.followup.send(result, ephemeral=True)
        await self.shop_view.refresh()


async def _open_custom_role(interaction: discord.Interaction, item: dict, shop_view: "ShopView"):
    user, guild = interaction.user, interaction.guild
    if guild is None or not isinstance(user, discord.Member):
        await interaction.response.send_message(
            "Custom roles live in a server, so open /shop in a server.", ephemeral=True
        )
        return
    if not guild.me.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "I need the **Manage Roles** permission in this server to make custom roles.",
            ephemeral=True,
        )
        return

    record = _custom_records(guild.id).get(str(user.id))
    if record is None and _eco.get_balance(user.id) < item["price"]:
        await interaction.response.send_message(
            f"You need **{_eco.format_currency(item['price'])}** for **{item['name']}**, "
            f"but you only have **{_eco.format_currency(_eco.get_balance(user.id))}**.",
            ephemeral=True,
        )
        return

    await interaction.response.send_modal(CustomRoleModal(item, record, shop_view))
    await shop_view.refresh() 

def _worn_shop_roles(member: discord.Member) -> list[tuple[str, str, discord.Role]]:
    guild = member.guild
    worn = []
    role_ids = _shop_role_ids(guild.id)
    for item in _all_items():
        if item["type"] != "title":
            continue
        role = guild.get_role(role_ids.get(item["id"], 0))
        if role is not None and role in member.roles:
            worn.append((f"title:{item['id']}", item["name"], role))
    record = _custom_records(guild.id).get(str(member.id))
    role = guild.get_role(record["role_id"]) if record else None
    if role is not None and role in member.roles:
        worn.append(("custom", record["name"], role))
    return worn


async def _remove_roles(interaction: discord.Interaction, values: list[str]) -> str:
    member, guild = interaction.user, interaction.guild
    if guild is None or not isinstance(member, discord.Member):
        return "Open /shop in a server to remove roles."
    if not guild.me.guild_permissions.manage_roles:
        return "I need the **Manage Roles** permission in this server to remove roles."

    wanted = {value: (label, role) for value, label, role in _worn_shop_roles(member)}
    chosen = [(v, *wanted[v]) for v in values if v in wanted]
    if not chosen:
        return "You aren't wearing those roles anymore."

    try:
        await member.remove_roles(*[role for _, _, role in chosen], reason="Removed via shop")
    except (discord.Forbidden, discord.HTTPException):
        return "I couldn't remove those roles. Make sure my role is above them."

    entry = inventory_data.setdefault(str(member.id), {})
    for value, label, _ in chosen:
        if value.startswith("title:") and entry.get("title") == ITEMS_BY_ID[value[6:]]["title"]:
            entry.pop("title", None)
    save_inventory(inventory_data)

    names = ", ".join(f"**{label}**" for _, label, _ in chosen)
    return (
        f"Removed {names}. "
    )


class RemoveRoleSelect(discord.ui.Select):
    def __init__(self, worn, shop_view: "ShopView"):
        options = [discord.SelectOption(label=label[:100], value=value) for value, label, _ in worn]
        super().__init__(
            placeholder="Choose roles to remove...",
            options=options,
            min_values=1,
            max_values=len(options),
        )
        self.shop_view = shop_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await _remove_roles(interaction, self.values)
        await interaction.edit_original_response(content=result, view=None)
        await self.shop_view.refresh()


class RemoveRoleView(discord.ui.View):
    def __init__(self, worn, shop_view: "ShopView"):
        super().__init__(timeout=60)
        self.add_item(RemoveRoleSelect(worn, shop_view))


def _option_description(item: dict, status: str | None = None) -> str:
    text = f"{item['price']:,} {_eco.symbol}"
    if status:
        text += f" • {status.capitalize()}"
    left = _stock_left(item)
    if left is not None:
        text += f" • {left} left" if left > 0 else " • Sold out"
    return text[:100]


class ItemSelect(discord.ui.Select):
    def __init__(self, category: str, user: discord.abc.User):
        items = _items_in_category(category)
        options = [
            discord.SelectOption(
                label=item["name"],
                value=item["id"],
                description=_option_description(item, _item_status(user, item)),
                emoji=item["emoji"],
            )
            for item in items[:25]
        ]
        if not options:
            options = [discord.SelectOption(label="Nothing here yet", value="_none")]
        super().__init__(
            placeholder=f"Choose from {CATEGORIES[category][0]}...",
            options=options,
            row=0,
            disabled=not items,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view 
        item = ITEMS_BY_ID[self.values[0]]
        if item["type"] == "custom_role":
            await _open_custom_role(interaction, item, view)
            return
        await interaction.response.defer()
        result = await _purchase(interaction, item)
        view.user = interaction.user
        view.rebuild_select()
        try:
            await interaction.edit_original_response(
                embed=_build_embed(interaction.user, view.category), view=view
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send(result, ephemeral=True)


class CategoryButton(discord.ui.Button):
    def __init__(self, key: str):
        name, emoji = CATEGORIES[key]
        super().__init__(label=name, emoji=emoji, style=discord.ButtonStyle.secondary, row=1)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        view.category = self.key
        view.rebuild_select()
        await interaction.response.edit_message(
            embed=_build_embed(interaction.user, view.category), view=view
        )


class ShopView(discord.ui.View):
    def __init__(self, owner_id: int, user: discord.abc.User):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.user = user
        self.interaction: discord.Interaction | None = None
        self.category = DEFAULT_CATEGORY
        self.item_select: ItemSelect | None = None
        self.category_buttons: dict[str, CategoryButton] = {}
        for key in CATEGORIES:
            button = CategoryButton(key)
            self.category_buttons[key] = button
            self.add_item(button)
        self.rebuild_select()

    def rebuild_select(self):
        if self.item_select is not None:
            self.remove_item(self.item_select)
        self.item_select = ItemSelect(self.category, self.user)
        self.add_item(self.item_select)
        for key, button in self.category_buttons.items():
            button.style = (
                discord.ButtonStyle.primary if key == self.category
                else discord.ButtonStyle.secondary
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "That's not your shop menu. Run /shop to open your own.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.secondary, emoji="🗑️", row=2)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Open /shop in a server to remove roles.", ephemeral=True
            )
            return
        worn = _worn_shop_roles(member)
        if not worn:
            await interaction.response.send_message(
                "You aren't wearing any shop roles in this server.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Which roles do you want to take off?",
            view=RemoveRoleView(worn, self),
            ephemeral=True,
        )

    async def refresh(self):
        if self.interaction is None:
            return
        try:
            self.user = self.interaction.user
            self.rebuild_select()
            await self.interaction.edit_original_response(
                embed=_build_embed(self.interaction.user, self.category), view=self
            )
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.interaction is not None:
            try:
                await self.interaction.edit_original_response(view=self)
            except discord.HTTPException:
                pass


def _build_inventory_embed(user: discord.abc.User) -> discord.Embed:
    owned_titles = inventory_data.get(str(user.id), {}).get("titles", [])

    guild = getattr(user, "guild", None)
    worn_role_ids = set()
    shop_role_ids = {}
    custom_record = None
    if guild is not None and isinstance(user, discord.Member):
        worn_role_ids = {r.id for r in user.roles}
        shop_role_ids = inventory_data.get(ROLES_KEY, {}).get(str(guild.id), {})
        custom_record = inventory_data.get(CUSTOM_KEY, {}).get(str(guild.id), {}).get(str(user.id))

    titles_by_name = {i["title"]: i for i in _all_items() if i["type"] == "title"}

    title_lines = []
    limited_lines = []
    for title in owned_titles:
        item = titles_by_name.get(title)
        emoji = item["emoji"] if item else "🏷️"
        status = " *(equipped)*" if item and shop_role_ids.get(item["id"]) in worn_role_ids else ""
        line = f"{emoji} **{title}**{status}"
        if item and item["category"] == "limited":
            limited_lines.append(line)
        else:
            title_lines.append(line)

    embed = discord.Embed(title=f"{user.display_name}'s Inventory", color=EMBED_COLOR)
    embed.set_thumbnail(url=user.display_avatar.url)

    if title_lines:
        embed.add_field(
            name=f"{CATEGORIES['general'][1]} {CATEGORIES['general'][0]}:",
            value="\n".join(title_lines)[:1024],
            inline=False,
        )

    if limited_lines:
        embed.add_field(
            name=f"{CATEGORIES['limited'][1]} {CATEGORIES['limited'][0]}:",
            value="\n".join(limited_lines)[:1024],
            inline=False,
        )

    if custom_record:
        role = guild.get_role(custom_record["role_id"]) if guild is not None else None
        role_text = role.mention if role is not None else f"**{custom_record['name']}**"
        status = " *(equipped)*" if role is not None and role.id in worn_role_ids else ""
        embed.add_field(
            name=f"{CATEGORIES['custom'][1]} {CATEGORIES['custom'][0]}:",
            value=f"🎨 {role_text} (`#{custom_record['color']:06X}`){status}",
            inline=False,
        )

    if not title_lines and not limited_lines and not custom_record:
        embed.description = "You don't own anything yet. Browse `/shop` to get started."
    return embed


def _equippable_items(member: discord.Member) -> list[tuple[str, str, str, bool]]:
    guild = member.guild
    worn_ids = {r.id for r in member.roles}
    role_ids = _shop_role_ids(guild.id)
    owned_titles = inventory_data.get(str(member.id), {}).get("titles", [])

    out = []
    for item in _all_items():
        if item["type"] == "title" and item["title"] in owned_titles:
            equipped = role_ids.get(item["id"]) in worn_ids
            out.append((f"title:{item['id']}", item["name"], item["emoji"], equipped))

    record = _custom_records(guild.id).get(str(member.id))
    if record:
        role = guild.get_role(record["role_id"])
        equipped = role is not None and role.id in worn_ids
        out.append(("custom", record["name"], CUSTOM_ROLE_ITEM["emoji"], equipped))
    return out


async def _equip_owned(interaction: discord.Interaction, value: str) -> str:
    member, guild = interaction.user, interaction.guild
    if guild is None or not isinstance(member, discord.Member):
        return "Open /inventory in a server to equip roles."
    if not guild.me.guild_permissions.manage_roles:
        return "I need the **Manage Roles** permission in this server to equip roles."

    if value == "custom":
        record = _custom_records(guild.id).get(str(member.id))
        if not record:
            return "You don't have a custom role yet. Get one in /shop."
        role = guild.get_role(record["role_id"])
        if role is None:
            return "Your custom role no longer exists. Re-create it in /shop."
        if role in member.roles:
            return f"You're already wearing {role.mention}."
        try:
            await member.add_roles(role, reason="Equipped from inventory")
        except (discord.Forbidden, discord.HTTPException):
            return "I couldn't give you that role. Make sure my role is above it."
        return f"Equipped your custom role {role.mention}."

    if value.startswith("title:"):
        item = ITEMS_BY_ID.get(value[6:])
        entry = inventory_data.get(str(member.id), {})
        if item is None or item["type"] != "title" or item["title"] not in entry.get("titles", []):
            return "You don't own that title."
        existing = guild.get_role(_shop_role_ids(guild.id).get(item["id"], 0))
        if existing is not None and existing in member.roles:
            return f"You're already wearing the **{item['title']}** role."
        try:
            await _equip_title_role(member, item)
        except (discord.Forbidden, discord.HTTPException):
            return "I couldn't give you that role. Make sure my role is above the title roles."
        entry["title"] = item["title"]
        save_inventory(inventory_data)
        return f"Equipped your **{item['title']}** role."

    return "I don't know how to equip that."


class EquipSelect(discord.ui.Select):
    def __init__(self, equippable):
        options = [
            discord.SelectOption(
                label=label[:100],
                value=value,
                emoji=emoji,
                description="Currently equipped" if equipped else "Click to equip",
            )
            for value, label, emoji, equipped in equippable[:25]
        ]
        super().__init__(placeholder="Choose an item to equip...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = await _equip_owned(interaction, self.values[0])
        await self.view.refresh()
        await interaction.followup.send(result, ephemeral=True)


class InventoryView(discord.ui.View):
    def __init__(self, owner_id: int, member: discord.Member):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.member = member
        self.interaction: discord.Interaction | None = None
        self._rebuild()

    def _rebuild(self):
        for child in list(self.children):
            if isinstance(child, EquipSelect):
                self.remove_item(child)
        equippable = _equippable_items(self.member)
        if equippable:
            self.add_item(EquipSelect(equippable))

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.secondary, emoji="🗑️", row=1)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Open /inventory in a server to remove roles.", ephemeral=True
            )
            return
        worn = _worn_shop_roles(member)
        if not worn:
            await interaction.response.send_message(
                "You aren't wearing any shop roles in this server.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Which roles do you want to take off?",
            view=RemoveRoleView(worn, self),
            ephemeral=True,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "That's not your inventory. Run /inventory to open your own.", ephemeral=True
            )
            return False
        return True

    async def refresh(self):
        if self.interaction is None:
            return
        member = self.member.guild.get_member(self.member.id) or self.member
        self.member = member
        self._rebuild()
        try:
            embed = _build_inventory_embed(member)
            embed.set_footer(text=INVENTORY_FOOTER)
            await self.interaction.edit_original_response(embed=embed, view=self)
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.interaction is not None:
            try:
                await self.interaction.edit_original_response(view=self)
            except discord.HTTPException:
                pass


def register(bot, *, balances_data, get_balance, save_balances, format_currency,
             symbol, name_allowed):
    _eco.balances_data = balances_data
    _eco.get_balance = get_balance
    _eco.save_balances = save_balances
    _eco.format_currency = format_currency
    _eco.symbol = symbol
    _eco.name_allowed = name_allowed  

    @bot.tree.command(name="shop", description="Browse the shop and spend your Amber")
    async def shop(interaction: discord.Interaction):
        view = ShopView(interaction.user.id, interaction.user)
        view.interaction = interaction
        await interaction.response.send_message(
            embed=_build_embed(interaction.user), view=view, ephemeral=True
        )

    @bot.tree.command(name="inventory", description="See the items you own (or someone else's)")
    @app_commands.describe(user="Whose inventory to view (defaults to you)")
    async def inventory(interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        embed = _build_inventory_embed(target)

        is_own = target.id == interaction.user.id
        if is_own and interaction.guild is not None and isinstance(interaction.user, discord.Member):
            view = InventoryView(interaction.user.id, interaction.user)
            if _equippable_items(interaction.user):
                view.interaction = interaction
                embed.set_footer(text=INVENTORY_FOOTER)
                await interaction.response.send_message(embed=embed, view=view)
                return
        await interaction.response.send_message(embed=embed)