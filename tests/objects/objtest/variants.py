"""Variant files: the portfolio pair, an encrypted pair and a signed light build.

These change how a file is stored or opened rather than what it draws, so they're separate
files: a theming tool has to cope with each of them.
"""
import datetime
import os
import subprocess

import pikepdf

from .build import save
from .palette import build_palettes
from .portfolio import build_portfolio


def encrypted(src, dst):
    """AES-256 with an empty user password, so the file opens without one."""
    subprocess.run(["qpdf", "--decode-level=none", "--compress-streams=n", "--object-streams=generate",
                    "--encrypt", "", "pdf-themes-owner", "256", "--", src, dst], check=True)


def self_signed(workdir):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pdf-themes test signer (not trusted)")])
    now = datetime.datetime(2026, 10, 3, tzinfo=datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    kp, cp = os.path.join(workdir, "signer-key.pem"), os.path.join(workdir, "signer-cert.pem")
    open(kp, "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    open(cp, "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    return kp, cp


def signed(src, dst, workdir):
    from pyhanko.sign import signers, fields
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    kp, cp = self_signed(workdir)
    signer = signers.SimpleSigner.load(kp, cp)
    with open(src, "rb") as inf:
        w = IncrementalPdfFileWriter(inf, strict=False)
        meta = signers.PdfSignatureMetadata(field_name="signature", reason="Test signature for pdf-themes",
                                            location="Bristol")
        with open(dst, "wb") as outf:
            signers.PdfSigner(meta, signer=signer).sign_pdf(w, output=outf)
    for f in (kp, cp):
        os.remove(f)


def main(outdir="out"):
    for pal in build_palettes():
        pdf = build_portfolio(pal)
        path = os.path.join(outdir, "portfolio-%s.pdf" % pal.name)
        save(pdf, path)
        print("wrote", path, os.path.getsize(path))
        enc = os.path.join(outdir, "objects-%s-encrypted.pdf" % pal.name)
        encrypted(os.path.join(outdir, "objects-%s.pdf" % pal.name), enc)
        print("wrote", enc, os.path.getsize(enc))
    sig = os.path.join(outdir, "objects-light-signed.pdf")
    signed(os.path.join(outdir, "objects-light.pdf"), sig, outdir)
    print("wrote", sig, os.path.getsize(sig))


if __name__ == "__main__":
    import sys
    main(*(sys.argv[1:2] or ["out"]))
