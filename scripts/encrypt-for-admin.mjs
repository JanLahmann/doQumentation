#!/usr/bin/env node
/**
 * Encrypts a string with the admin password using AES-256-GCM + PBKDF2.
 * The output can be stored in ADMIN_ENCRYPTED_URLS env var.
 *
 * Usage:
 *   ADMIN_PASSWORD=secret node scripts/encrypt-for-admin.mjs "https://example.com/share/abc123"
 *
 * Output: base64 blob (salt:iv:ciphertext)
 *
 * To encrypt multiple URLs as a JSON object:
 *   ADMIN_PASSWORD=secret node scripts/encrypt-for-admin.mjs --json '{"umamiShare":"https://..."}'
 */

import { webcrypto } from 'node:crypto';

const password = process.env.ADMIN_PASSWORD;
if (!password) {
  console.error('Error: ADMIN_PASSWORD env var is required');
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error('Usage: ADMIN_PASSWORD=secret node scripts/encrypt-for-admin.mjs <plaintext>');
  console.error('       ADMIN_PASSWORD=secret node scripts/encrypt-for-admin.mjs --json \'{"key":"value"}\'');
  process.exit(1);
}

const isJson = args[0] === '--json';
const plaintext = isJson ? args[1] : args[0];

if (!plaintext) {
  console.error('Error: no plaintext provided');
  process.exit(1);
}

async function encrypt(plaintext, password) {
  const enc = new TextEncoder();
  const salt = webcrypto.getRandomValues(new Uint8Array(16));
  const iv = webcrypto.getRandomValues(new Uint8Array(12));

  const keyMaterial = await webcrypto.subtle.importKey(
    'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']
  );
  const key = await webcrypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt']
  );

  const ciphertext = await webcrypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    enc.encode(plaintext)
  );

  // Pack as base64: salt(16) + iv(12) + ciphertext
  const packed = new Uint8Array(salt.length + iv.length + ciphertext.byteLength);
  packed.set(salt, 0);
  packed.set(iv, salt.length);
  packed.set(new Uint8Array(ciphertext), salt.length + iv.length);

  return Buffer.from(packed).toString('base64');
}

const result = await encrypt(plaintext, password);
console.log(result);
