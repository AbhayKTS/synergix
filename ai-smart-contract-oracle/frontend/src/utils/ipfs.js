export const ipfsToHttp = (cid, gateway = 'https://ipfs.io/ipfs/') => {
  if (!cid) return null;
  if (cid.startsWith('http')) return cid;
  return `${gateway}${cid.replace('ipfs://', '')}`;
};
