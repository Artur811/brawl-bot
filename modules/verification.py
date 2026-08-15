VERIFY_IMAGES = {
    "device": "https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/a/4/c/b/a4cb7f66e45935445932f8d966013463406a251e.png",
    "authenticator": "https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/8/d/a/5/8da5d76034856021ad807288f8c8e8a43c66a8b4.png",
    "email": "https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/4/2/6/8/4268f5cf79d76d381d13648d545b8929d562ae08.png",
}


def verification_text(kind: str) -> str:
    if kind == "email":
        return (
            "📧 <b>2FA — E-mail</b>\n\n"
            "Բացիր քո հաստատված E-mail-ը և մուտքագրիր Roblox-ի ուղարկած կոդը միայն Roblox-ի պաշտոնական մուտքի էջում։\n\n"
            "⚠️ Կոդը <b>ոչ մի դեպքում մի ուղարկիր</b> Games Vault Shop-ին կամ ադմինին։"
        )
    if kind == "authenticator":
        return (
            "🔐 <b>2FA — Authenticator</b>\n\n"
            "Բացիր քո Authenticator հավելվածը և օգտագործիր այնտեղ երևացող կոդը միայն Roblox-ի պաշտոնական մուտքի էջում։\n\n"
            "⚠️ Authenticator-ի կոդը <b>ոչ մի դեպքում մի ուղարկիր</b> Games Vault Shop-ին կամ ադմինին։"
        )
    return (
        "📱 <b>2FA — Այլ սարքով հաստատում</b>\n\n"
        "Բացիր Roblox-ը այն հեռախոսում կամ պլանշետում, որտեղ քո հաշիվը արդեն մուտք գործած է։ Հաստատիր միայն այն մուտքը, որը դու ես սկսել։\n\n"
        "⚠️ Եթե մուտքը քոնը չէ՝ մերժիր այն։ Կոդ կամ գաղտնաբառ մեզ մի ուղարկիր։"
    )
