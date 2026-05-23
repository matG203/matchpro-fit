const bcrypt = require('bcryptjs');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function main() {
  const [, , login, password] = process.argv;
  if (!login || !password || password.length < 8) {
    console.error('Usage: npm run reset-password -- email-or-username NewPassword123');
    process.exit(1);
  }
  const user = await prisma.user.findFirst({
    where: { OR: [{ email: login.toLowerCase() }, { username: login.toLowerCase() }] },
  });
  if (!user) {
    console.error('No user found for that email or username.');
    process.exit(1);
  }
  await prisma.user.update({
    where: { id: user.id },
    data: { passwordHash: await bcrypt.hash(password, 12) },
  });
  console.log(`Password reset for ${user.username}.`);
}

main().finally(() => prisma.$disconnect());
