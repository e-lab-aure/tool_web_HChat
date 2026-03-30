/**
 * HChat Crypto Module
 *
 * Priorite : Web Crypto API (disponible en HTTPS / localhost)
 * Fallback  : AES-256-GCM + PBKDF2-HMAC-SHA256 pure JavaScript
 *             compatible avec la sortie native - meme format de ciphertext.
 *
 * Format des messages chiffres : JSON.stringify({ iv: "<hex 24c>", ct: "<base64>" })
 * Le champ ct contient : ciphertext || tag GCM (16 octets) en base64.
 *
 * Les deux implementations produisent et consomment le meme format.
 * Iterations PBKDF2 : 120 000 (meme valeur partout).
 */

window.HChatCrypto = (() => {
    'use strict';

    const PBKDF2_ITER = 120000;

    // TextEncoder / TextDecoder : polyfill minimal pour navigateurs tres anciens
    const _enc = (typeof TextEncoder !== 'undefined')
        ? new TextEncoder()
        : { encode: s => { const b = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i) & 0xff; return b; } };
    const _dec = (typeof TextDecoder !== 'undefined')
        ? new TextDecoder()
        : { decode: b => { let s = ''; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return s; } };

    /* ------------------------------------------------------------------
       Utilitaires communs
    ------------------------------------------------------------------ */
    function hexToBytes(hex) {
        const b = new Uint8Array(hex.length >>> 1);
        for (let i = 0; i < b.length; i++) b[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
        return b;
    }
    function bytesToHex(b) {
        let s = '';
        for (let i = 0; i < b.length; i++) s += b[i].toString(16).padStart(2, '0');
        return s;
    }
    function b64enc(b) { return btoa(String.fromCharCode.apply(null, b)); }
    function b64dec(s) { return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }
    function safeRandBytes(n) {
        const buf = new Uint8Array(n);
        if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
            // getRandomValues est disponible meme sans contexte securise
            crypto.getRandomValues(buf);
        } else {
            for (let i = 0; i < n; i++) buf[i] = (Math.random() * 256) | 0;
        }
        return buf;
    }

    /* ------------------------------------------------------------------
       Detection : Web Crypto utilisable ?
       crypto.subtle est null/undefined hors contexte securise (HTTP)
    ------------------------------------------------------------------ */
    const useNative = (() => {
        try {
            return (
                typeof crypto !== 'undefined' &&
                crypto.subtle != null &&
                typeof crypto.subtle.importKey === 'function'
            );
        } catch { return false; }
    })();

    /* ==================================================================
       CHEMIN NATIF - Web Crypto API
    ================================================================== */
    async function nativeDeriveKey(password, saltHex) {
        const km = await crypto.subtle.importKey(
            'raw', _enc.encode(password), 'PBKDF2', false, ['deriveKey']
        );
        return crypto.subtle.deriveKey(
            { name: 'PBKDF2', salt: hexToBytes(saltHex), iterations: PBKDF2_ITER, hash: 'SHA-256' },
            km,
            { name: 'AES-GCM', length: 256 },
            false,
            ['encrypt', 'decrypt']
        );
    }

    async function nativeEncrypt(key, plaintext) {
        const iv = safeRandBytes(12);
        const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, _enc.encode(plaintext));
        return { iv: bytesToHex(iv), ct: b64enc(new Uint8Array(ct)) };
    }

    async function nativeDecrypt(key, iv, ct) {
        try {
            const plain = await crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: hexToBytes(iv) }, key, b64dec(ct)
            );
            return _dec.decode(plain);
        } catch { return null; }
    }

    /* ==================================================================
       CHEMIN FALLBACK - AES-256-GCM + PBKDF2-HMAC-SHA256 pur JS
       Conforme FIPS 197, NIST SP 800-38D, RFC 8018
    ================================================================== */

    /* --- SHA-256 (RFC 6234) --- */
    const _K32 = new Int32Array([
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ]);

    function _rotr(x, n) { return (x >>> n) | (x << (32 - n)); }

    function sha256(data) {
        let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a;
        let h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;

        const len = data.length;
        const extra = (64 - ((len + 9) % 64)) % 64;
        const msg = new Uint8Array(len + 1 + extra + 8);
        msg.set(data);
        msg[len] = 0x80;
        // Encode bit length as 64-bit big-endian (assume length < 2^32 bits)
        const bits = len * 8;
        for (let i = 0; i < 4; i++) msg[msg.length - 1 - i] = (bits >>> (i * 8)) & 0xff;

        const W = new Int32Array(64);
        for (let o = 0; o < msg.length; o += 64) {
            for (let i = 0; i < 16; i++) {
                W[i] = (msg[o+i*4]<<24)|(msg[o+i*4+1]<<16)|(msg[o+i*4+2]<<8)|msg[o+i*4+3];
            }
            for (let i = 16; i < 64; i++) {
                const s0 = _rotr(W[i-15],7)^_rotr(W[i-15],18)^(W[i-15]>>>3);
                const s1 = _rotr(W[i-2],17)^_rotr(W[i-2],19)^(W[i-2]>>>10);
                W[i] = (W[i-16]+s0+W[i-7]+s1)|0;
            }
            let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
            for (let i = 0; i < 64; i++) {
                const S1=_rotr(e,6)^_rotr(e,11)^_rotr(e,25);
                const ch=(e&f)^(~e&g);
                const t1=(h+S1+ch+_K32[i]+W[i])|0;
                const S0=_rotr(a,2)^_rotr(a,13)^_rotr(a,22);
                const maj=(a&b)^(a&c)^(b&c);
                const t2=(S0+maj)|0;
                h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;
            }
            h0=(h0+a)|0;h1=(h1+b)|0;h2=(h2+c)|0;h3=(h3+d)|0;
            h4=(h4+e)|0;h5=(h5+f)|0;h6=(h6+g)|0;h7=(h7+h)|0;
        }
        const out = new Uint8Array(32);
        const hv = [h0,h1,h2,h3,h4,h5,h6,h7];
        for (let i = 0; i < 8; i++) {
            out[i*4]=(hv[i]>>>24)&0xff;out[i*4+1]=(hv[i]>>>16)&0xff;
            out[i*4+2]=(hv[i]>>>8)&0xff;out[i*4+3]=hv[i]&0xff;
        }
        return out;
    }

    /* --- HMAC-SHA256 (RFC 2104) --- */
    function hmac256(key, data) {
        const BS = 64;
        if (key.length > BS) key = sha256(key);
        const k = new Uint8Array(BS);
        k.set(key);
        const ipad = new Uint8Array(BS + data.length);
        const opad = new Uint8Array(BS + 32);
        for (let i = 0; i < BS; i++) { ipad[i] = k[i] ^ 0x36; opad[i] = k[i] ^ 0x5c; }
        ipad.set(data, BS);
        opad.set(sha256(ipad), BS);
        return sha256(opad);
    }

    /* --- PBKDF2-HMAC-SHA256 (RFC 8018 section 5.2) --- */
    function pbkdf2(password, salt, iterations, dkLen) {
        const pw = typeof password === 'string' ? _enc.encode(password) : password;
        const blocks = Math.ceil(dkLen / 32);
        const dk = new Uint8Array(blocks * 32);
        for (let b = 1; b <= blocks; b++) {
            const blk = new Uint8Array(salt.length + 4);
            blk.set(salt);
            blk[salt.length]=(b>>>24)&0xff;blk[salt.length+1]=(b>>>16)&0xff;
            blk[salt.length+2]=(b>>>8)&0xff;blk[salt.length+3]=b&0xff;
            let u = hmac256(pw, blk);
            const f = u.slice();
            for (let i = 1; i < iterations; i++) {
                u = hmac256(pw, u);
                for (let j = 0; j < 32; j++) f[j] ^= u[j];
            }
            dk.set(f, (b - 1) * 32);
        }
        return dk.slice(0, dkLen);
    }

    /* --- AES-256 (FIPS 197) --- */
    // S-box : tableau de substitution non-lineaire
    const _SB = new Uint8Array([
        0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
        0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
        0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
        0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
        0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
        0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
        0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
        0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
        0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
        0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
        0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
        0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
        0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
        0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
        0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
    ]);

    // Multiplication par 2 dans GF(2^8) avec polynome reducteur 0x11b
    function _xt(b) { return ((b << 1) ^ ((b >>> 7) * 0x1b)) & 0xff; }

    // Expansion de cle AES-256 -> 240 octets (60 mots de 4 octets)
    function _aesKS(key) {
        const rcon = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d];
        const w = new Uint8Array(240);
        w.set(key);
        for (let i = 32; i < 240; i += 4) {
            const col = i >>> 2;
            let t0=w[i-4],t1=w[i-3],t2=w[i-2],t3=w[i-1];
            if (col % 8 === 0) {
                const tmp=t0;
                t0=_SB[t1]^rcon[col/8-1]; t1=_SB[t2]; t2=_SB[t3]; t3=_SB[tmp];
            } else if (col % 8 === 4) {
                t0=_SB[t0]; t1=_SB[t1]; t2=_SB[t2]; t3=_SB[t3];
            }
            w[i]=w[i-32]^t0; w[i+1]=w[i-31]^t1; w[i+2]=w[i-30]^t2; w[i+3]=w[i-29]^t3;
        }
        return w;
    }

    // Chiffrement d'un bloc AES (16 octets) avec la cle etendue
    function _aesB(blk, rk) {
        let s = blk.slice();
        for (let i = 0; i < 16; i++) s[i] ^= rk[i]; // AddRoundKey round 0
        for (let r = 1; r <= 14; r++) {
            // SubBytes
            for (let i = 0; i < 16; i++) s[i] = _SB[s[i]];
            // ShiftRows (etat colonne-majeur : index = col*4 + row)
            const t = new Uint8Array(16);
            t[0]=s[0];  t[1]=s[5];  t[2]=s[10]; t[3]=s[15];
            t[4]=s[4];  t[5]=s[9];  t[6]=s[14]; t[7]=s[3];
            t[8]=s[8];  t[9]=s[13]; t[10]=s[2]; t[11]=s[7];
            t[12]=s[12];t[13]=s[1]; t[14]=s[6]; t[15]=s[11];
            s = t;
            // MixColumns (omis au dernier round)
            if (r < 14) {
                for (let c = 0; c < 4; c++) {
                    const b0=s[c*4],b1=s[c*4+1],b2=s[c*4+2],b3=s[c*4+3];
                    s[c*4]  =_xt(b0)^_xt(b1)^b1^b2^b3;
                    s[c*4+1]=b0^_xt(b1)^_xt(b2)^b2^b3;
                    s[c*4+2]=b0^b1^_xt(b2)^_xt(b3)^b3;
                    s[c*4+3]=_xt(b0)^b0^b1^b2^_xt(b3);
                }
            }
            // AddRoundKey
            const base = r * 16;
            for (let i = 0; i < 16; i++) s[i] ^= rk[base + i];
        }
        return s;
    }

    /* --- AES-GCM (NIST SP 800-38D) --- */

    // Multiplication dans GF(2^128) avec polynome reducteur de GCM
    function _ghashMul(X, Y) {
        const Z = new Uint8Array(16);
        const V = Y.slice();
        for (let i = 0; i < 128; i++) {
            if ((X[i >>> 3] >>> (7 - (i & 7))) & 1) {
                for (let j = 0; j < 16; j++) Z[j] ^= V[j];
            }
            const lsb = V[15] & 1;
            for (let j = 15; j > 0; j--) V[j] = (V[j] >>> 1) | ((V[j-1] & 1) << 7);
            V[0] >>>= 1;
            if (lsb) V[0] ^= 0xe1;
        }
        return Z;
    }

    // GHASH : hachage authentifie sur donnees multiples de 16 octets
    function _ghash(H, data) {
        let y = new Uint8Array(16);
        for (let i = 0; i < data.length; i += 16) {
            for (let j = 0; j < 16; j++) y[j] ^= data[i + j];
            y = _ghashMul(y, H);
        }
        return y;
    }

    // Incremente le compteur 32 bits (big-endian, octets 12-15)
    function _incCtr(ctr) {
        for (let j = 15; j >= 12; j--) { if (++ctr[j] !== 0) break; }
    }

    // GCTR : mode compteur AES pour chiffrement/dechiffrement
    function _gctr(rk, icb, data) {
        const out = new Uint8Array(data.length);
        const cb = icb.slice();
        for (let i = 0; i < data.length; i += 16) {
            const ks = _aesB(cb, rk);
            const n = Math.min(16, data.length - i);
            for (let j = 0; j < n; j++) out[i + j] = data[i + j] ^ ks[j];
            _incCtr(cb);
        }
        return out;
    }

    // Pad de donnees a un multiple de 16 octets (zeros)
    function _pad16(data) {
        const r = data.length % 16;
        if (r === 0) return data;
        const out = new Uint8Array(data.length + (16 - r));
        out.set(data);
        return out;
    }

    // Encode la longueur en bits dans 16 octets (len(AAD) || len(C))
    // AAD vide = 0, cLen en octets converti en bits
    function _lenBlk(cLen) {
        const b = new Uint8Array(16); // les 8 premiers = 0 (AAD vide)
        const bits = cLen * 8;
        b[8]=(bits/0x1000000/0x1000000)|0; // pour les tres grands textes
        b[12]=(bits>>>24)&0xff; b[13]=(bits>>>16)&0xff;
        b[14]=(bits>>>8)&0xff;  b[15]=bits&0xff;
        return b;
    }

    function _gcmEncrypt(keyBytes, iv12, plaintext) {
        const rk = _aesKS(keyBytes);
        const H  = _aesB(new Uint8Array(16), rk);

        // J0 = IV(96b) || 0^31 || 1
        const J0 = new Uint8Array(16);
        J0.set(iv12); J0[15] = 1;

        // Premier compteur de chiffrement = inc32(J0)
        const ctr0 = J0.slice();
        _incCtr(ctr0);

        const ct = _gctr(rk, ctr0, plaintext);

        // Tag = GHASH(H, pad(C) || lenBlk) XOR E(K, J0)
        const padC = _pad16(ct);
        const ghIn = new Uint8Array(padC.length + 16);
        ghIn.set(padC);
        ghIn.set(_lenBlk(ct.length), padC.length);
        const S   = _ghash(H, ghIn);
        const EJ0 = _aesB(J0, rk);
        const tag = new Uint8Array(16);
        for (let i = 0; i < 16; i++) tag[i] = S[i] ^ EJ0[i];

        // Sortie : ciphertext || tag (meme format que Web Crypto)
        const out = new Uint8Array(ct.length + 16);
        out.set(ct);
        out.set(tag, ct.length);
        return out;
    }

    function _gcmDecrypt(keyBytes, iv12, ctWithTag) {
        if (ctWithTag.length < 16) return null;
        const ct  = ctWithTag.subarray(0, ctWithTag.length - 16);
        const tag = ctWithTag.subarray(ctWithTag.length - 16);

        const rk = _aesKS(keyBytes);
        const H  = _aesB(new Uint8Array(16), rk);
        const J0 = new Uint8Array(16);
        J0.set(iv12); J0[15] = 1;

        // Verification du tag avant dechiffrement (Authenticated Encryption)
        const padC = _pad16(ct);
        const ghIn = new Uint8Array(padC.length + 16);
        ghIn.set(padC);
        ghIn.set(_lenBlk(ct.length), padC.length);
        const S   = _ghash(H, ghIn);
        const EJ0 = _aesB(J0, rk);
        let diff = 0;
        for (let i = 0; i < 16; i++) diff |= (tag[i] ^ (S[i] ^ EJ0[i]));
        if (diff !== 0) return null; // Tag invalide = message falsifie

        const ctr0 = J0.slice();
        _incCtr(ctr0);
        return _gctr(rk, ctr0, ct);
    }

    /* ------------------------------------------------------------------
       Wrappers fallback (meme signature que le chemin natif)
    ------------------------------------------------------------------ */
    function jsDeriveKey(password, saltHex) {
        return pbkdf2(password, hexToBytes(saltHex), PBKDF2_ITER, 32);
    }

    function jsEncrypt(keyBytes, plaintext) {
        const iv = safeRandBytes(12);
        const ct = _gcmEncrypt(keyBytes, iv, _enc.encode(plaintext));
        return { iv: bytesToHex(iv), ct: b64enc(ct) };
    }

    function jsDecrypt(keyBytes, iv, ctB64) {
        const pt = _gcmDecrypt(keyBytes, hexToBytes(iv), b64dec(ctB64));
        return pt ? _dec.decode(pt) : null;
    }

    /* ==================================================================
       INTERFACE PUBLIQUE
       Etat interne : _key (CryptoKey ou Uint8Array selon le chemin)
    ================================================================== */
    let _key  = null;
    let _mode = useNative ? 'native' : 'js';

    /**
     * Derive la cle AES-256 depuis le mot de passe et le sel.
     * Doit etre appelee une seule fois a l'initialisation de la session.
     *
     * @param {string} password  Mot de passe en clair
     * @param {string} saltHex   Sel hexadecimal (fourni par le serveur)
     * @returns {Promise<void>}
     */
    async function deriveKey(password, saltHex) {
        if (_mode === 'native') {
            _key = await nativeDeriveKey(password, saltHex);
        } else {
            // PBKDF2 synchrone mais couteux : libere le thread via setTimeout
            _key = await new Promise((resolve, reject) => {
                setTimeout(() => {
                    try { resolve(jsDeriveKey(password, saltHex)); }
                    catch (e) { reject(e); }
                }, 20);
            });
        }
    }

    /**
     * Chiffre un texte en clair.
     * @param {string} plaintext  Texte a chiffrer
     * @returns {Promise<string>} JSON serialise { iv, ct }
     */
    async function encrypt(plaintext) {
        if (!_key) throw new Error('Cle non initialisee');
        let obj;
        if (_mode === 'native') {
            obj = await nativeEncrypt(_key, plaintext);
        } else {
            obj = jsEncrypt(_key, plaintext);
        }
        return JSON.stringify(obj);
    }

    /**
     * Dechiffre un payload JSON { iv, ct }.
     * @param {string} payload  Chaine JSON chiffree
     * @returns {Promise<string|null>} Texte en clair ou null si echec
     */
    async function decrypt(payload) {
        if (!_key) return null;
        try {
            const { iv, ct } = typeof payload === 'string' ? JSON.parse(payload) : payload;
            if (_mode === 'native') return await nativeDecrypt(_key, iv, ct);
            return jsDecrypt(_key, iv, ct);
        } catch { return null; }
    }

    /** Indique si le chemin natif (Web Crypto) est utilise. */
    function isNative() { return _mode === 'native'; }

    return { deriveKey, encrypt, decrypt, isNative };
})();
