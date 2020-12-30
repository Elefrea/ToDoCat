import discord
from discord.ext import commands
import asyncio

class ModificationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(aliases=['c'], case_insensitive=True)
    async def create(self, ctx, liste=None, *members: discord.Member):
        if not liste:
            await ctx.send("Please enter the liste name you want to create")
            return
        
        #check if the list exists
        l_exists = await self.check_liste(ctx.author.id, liste) #if liste exists return id_liste
        if l_exists:
            await ctx.send("You already have a liste named {}".format(liste))
            return

        #check if the main user exists
        user = await self.check_user(ctx.author.id)

        #set the mode
        party = False
        mode = False
        if not len(members) == 0:
            party=True
            #give permissions to members
            await ctx.send("Do you want the party member to be able to modify the party liste {} ? y or n ".format(liste.capitalize()))
            try:
                msg = await self.bot.wait_for(
                    "message",
                    timeout=17,
                    check=lambda message: message.author == ctx.author 
                                        and message.channel == ctx.channel
                )
                if msg.content.lower() == "y" or msg.content.lower() == "yes":
                    mode = True #mode true = everyone can modify
            except asyncio.TimeoutError:
                await ctx.send("No respond, by default only <@{}> will be able to modify the list".format(ctx.author.id))
            
            #create liste for all members that can be added
            (msg, not_added_member) = await self.add_members(ctx.author.id, members, liste, ctx.message.id, None)
            await self.create_liste(ctx.author.id, ctx.message.id, liste.lower(), ctx.author.id, mode, party)
            await ctx.send("{} \nParty List {} successfully created! {} users have access".format(msg, liste.lower(), len(members) + 1 - not_added_member))
            return 

        #create list for main user
        await self.create_liste(ctx.author.id, ctx.message.id, liste.lower(), ctx.author.id, mode, party)

        await ctx.send("Liste {} successfully created, let's be productif miaw ;)".format(liste))

    @commands.command(aliases=['j'], case_insensitive=True)
    async def join(self, ctx, liste=None, *members: discord.Member):
        if not liste or len(members) == 0:
            await ctx.send("You have to specify an existing liste and at least ping one member to add")
            return

        id_liste = await self.check_liste(ctx.author.id, liste) #checks if a member already has a list with that name
        if not id_liste:
            await ctx.send("You have no liste named {}".format(liste))
            return

        await self.bot.con.execute("UPDATE listes SET party=True WHERE id_liste=$1", id_liste)
        (msg, not_added_member) = await self.add_members(ctx.author.id, members, liste, id_liste, None)

        await ctx.send("{} \nParty List {} successfully updated! {} users added".format(msg, liste.lower(), len(members) - not_added_member))

    @commands.command(aliases=['a'], help='$add "task_name" "list_name add a task to a to do list', case_insensitive=True)
    async def add(self, ctx, task=None, liste=None):
        if(task == None or liste == None):
            await ctx.send('Please write the commands as such :\n $add "task_name" "list_name"')
            return
        liste = liste.lower()
        task = task.lower()
    
        user = await self.check_user(ctx.author.id)

        l_name = await self.bot.con.fetchrow("SELECT * FROM main WHERE id_user=$1 AND l_name=$2", ctx.author.id, liste.lower())
        #if not _name for user, create list and add task
        if not l_name:
            await self.create_liste(ctx.author.id, ctx.message.id,liste, ctx.author.id, False, False)

        t_exists = await self.bot.con.fetch("SELECT id_task FROM main WHERE id_user=$1 AND l_name=$2 AND t_name=$3", ctx.author.id, liste.lower(), task.lower())

        if t_exists:
            await ctx.send("Task {} already exists in {}".format(task,liste))    
            return

        #add task to an existing liste
        await self.add_task(ctx.author.id, liste, ctx.message.id, task)
        await ctx.send('{} successfully added to {} !'.format(task, liste))

    @commands.command(aliases=["remove", "del"], case_insensitive=True)
    async def delete(self, ctx,liste=None,task=None):
        if not liste:
            await ctx.send("Enter the liste, task you want to remove")
            return

        id_liste = await self.bot.con.fetchval("SELECT id_liste FROM main WHERE id_user=$1 AND l_name=$2", ctx.author.id, liste.lower())
        if not id_liste:
            await ctx.send(" You have no liste named: {} ".format(liste))
            return

        if not task:
            await ctx.send("Are you sure you want to remove the entire {} liste ? type y or n".format(liste))
            try:
                msg = await self.bot.wait_for(
                    "message",
                    timeout=17,
                    check=lambda message: message.author == ctx.author 
                                        and message.channel == ctx.channel
                )
                if msg.content.lower() == "y" or msg.content.lower() == "yes":
                    await self.delete_liste(ctx, id_liste, ctx.author.id, liste) #DONNER DIRECTEMENT ID LISTE
                    return

                await ctx.send("{} has not been deleted".format(liste))

            except asyncio.TimeoutError:
                await ctx.send("{} has not been deleted".format(liste))
            return

        id_task = await self.bot.con.fetchval("SELECT id_task FROM main WHERE id_liste=$1 AND t_name=$2", id_liste, task.lower())
        if not id_task:
            await ctx.send(" You have no task named: {} ".format(task))
            return

        await self.delete_task(id_task, id_liste, ctx.author.id)
        await ctx.send("{} successfully deleted".format(task))
    
    @commands.command(aliases=["achieved", "finished"], case_insensitive=True)
    async def done(self, ctx, liste=None, task=None):
        if not liste or not task:
            await ctx.send("Please specify the task you achieved\n Enter: $done [liste name] [task name]")
            return
        
        #VERIFIER SI TASK LISTE EXISTS ;)

        #set task to achieved
        stat_task = await self.check_task(ctx.author.id, liste, task)

        if stat_task and not stat_task[1]:
            await self.bot.con.execute("UPDATE tasks SET achieved=True WHERE id_task=$1", stat_task[0])

            #update lists stats
            id_liste = await self.bot.con.fetchval("SELECT id_liste FROM main WHERE id_user=$1 AND l_name=$2", ctx.author.id, liste.lower())
            liste_nb_achieved = await self.bot.con.fetchval("SELECT nb_achieved FROM listes WHERE id_liste=$1", id_liste)
            await self.bot.con.execute("UPDATE listes SET nb_achieved=$1 WHERE id_liste=$2", liste_nb_achieved+1, id_liste)
            #update users stats
            users = await self.bot.con.fetch("SELECT id_user FROM main WHERE id_liste=$1", id_liste)
            for id_user in users:
                user = await self.bot.con.fetchrow("SELECT * FROM users WHERE id_user=$1", id_user[0])
                await self.bot.con.execute("UPDATE users SET nb_achieved=$1 WHERE id_user=$2", user['nb_achieved']+1, id_user[0])
            
            await ctx.send("Congratulation on achieving your task :partying_face:")
            return

        if stat_task:
            await ctx.send("Task already achieved")
            return

        await ctx.send("Task doesn't exist")

    ''' Database calls '''
    async def check_user(self,id):
        user = await self.bot.con.fetch("SELECT * FROM users WHERE id_user=$1", id)

        #if not user create a new user
        if not user:
            await self.bot.con.execute("INSERT INTO users (id_user, nb_tasks, nb_lists,nb_achieved) VALUES ($1,0,0,0)",id)
            
        return await self.bot.con.fetchrow("SELECT * FROM users WHERE id_user=$1", id)

    async def check_liste(self, id, liste):
        return await self.bot.con.fetchval("SELECT id_liste FROM main WHERE id_user=$1 AND l_name=$2", id, liste.lower())

    async def check_task(self, id, liste, task):
        id_liste = await self.bot.con.fetchval("SELECT id_liste FROM main WHERE id_user=$1 AND l_name=$2", id, liste.lower())
        return await self.bot.con.fetchrow("SELECT id_task, achieved FROM tasks WHERE id_liste=$1 AND t_name=$2", id_liste, task.lower())

    async def create_liste(self,id_user, id_liste, liste, admin, mode, party):
            #insert list in list
            if id_user == admin:
                await self.bot.con.execute("INSERT INTO listes (id_liste, nb_tasks, nb_achieved, l_name, admin, mode, party) VALUES ($1,0,0,$2,$3,$4,$5)",id_liste,liste.lower(), admin, mode, party)
            liste_el = await self.bot.con.fetchrow("SELECT * FROM listes WHERE id_liste=$1", id_liste) 
            #insert liste in main
            await self.bot.con.execute("INSERT INTO main (id_user, id_liste, l_name, id_task, t_name) VALUES ($1,$2,$3,NULL,NULL)",id_user,id_liste,liste.lower())

            #upading the user's stats
            user = await self.bot.con.fetchrow("SELECT * FROM users WHERE id_user=$1", id_user)
            
            if liste_el == None:
                await self.bot.con.execute("UPDATE users SET nb_lists=$1 WHERE id_user=$2", user['nb_lists']+1, id_user)
                return
            await self.bot.con.execute("UPDATE users SET nb_lists=$1, nb_tasks=$2, nb_achieved=$3 WHERE id_user=$4", user['nb_lists']+1, user['nb_tasks']+liste_el['nb_tasks'], user['nb_achieved']+liste_el['nb_achieved'], id_user)

    async def add_members(self, author, members, liste, id_liste, mode):
        party = True
        not_added_member = 0
        msg = ""
        for member in members:
            l_exists_for_member = await self.check_liste(member.id, liste) #checks if a member already has a list with that name returns the id_liste
            if l_exists_for_member:
                    msg = msg + "Member <@{}> already has a list named {}, she/he hasn't been added to the party\n".format(member.id, liste.capitalize())
                    not_added_member = not_added_member + 1
            elif not author == member.id:
                await self.check_user(member.id)
                await self.create_liste(member.id, id_liste, liste.lower(), author, mode, party)
        return (msg, not_added_member)

    async def add_task(self,id_user, liste, id_task, task):
 
            #find id_liste to udapte mains and liste table#
            id_liste = await self.bot.con.fetchval("SELECT id_liste FROM main WHERE id_user=$1 AND l_name=$2", id_user, liste)
            await self.bot.con.execute("INSERT INTO main (id_user, id_liste, l_name, id_task, t_name) VALUES ($1,$2,$3,$4,$5)",id_user,id_liste,liste.lower(),id_task,task.lower())
            liste = await self.bot.con.fetchrow("SELECT * FROM listes WHERE id_liste=$1", id_liste)
            await self.bot.con.execute("UPDATE listes SET nb_tasks=$1 WHERE id_liste=$2", liste['nb_tasks']+1, id_liste)
            ####

            #Insert task
            await self.bot.con.execute("INSERT INTO tasks (id_task, id_liste, t_name, important, urgent, achieved) VALUES ($1,$2,$3,False,False,False)",id_task,id_liste,task.lower())

            #IF PARTY LIST UPDATES ALL USERS
            users = await self.bot.con.fetch("SELECT id_user FROM main WHERE id_liste=$1", id_liste)
            for user in set(users):
                #upading the user's stats
                nb_tasks = await self.bot.con.fetchval("SELECT nb_tasks FROM users WHERE id_user=$1", user[0])
                await self.bot.con.execute("UPDATE users SET nb_tasks=$1 WHERE id_user=$2", nb_tasks+1, user[0])

    async def delete_liste(self, ctx, id_liste, id_user, liste):
        admin = await self.bot.con.fetchval("SELECT admin FROM listes WHERE id_liste=$1", id_liste)
        if id_user == admin:
            nb_tasks = await self.bot.con.fetchval("SELECT nb_tasks FROM listes WHERE id_liste=$1", id_liste)
            
            #find users_id and upading the users's stats
            id_users = await self.bot.con.fetch("SELECT id_user FROM main WHERE id_liste=$1", id_liste)
            for all_id_user in set(id_users):
                user = await self.bot.con.fetchrow("SELECT * FROM users WHERE id_user=$1", all_id_user[0])
                await self.bot.con.execute("UPDATE users SET nb_tasks=$1, nb_lists=$2 WHERE id_user=$3", user['nb_tasks']-nb_tasks, user['nb_lists']-1, all_id_user[0])

            #del listes and tasks from the other tables
            await self.bot.con.execute("DELETE FROM listes WHERE id_liste=$1", id_liste)
            await self.bot.con.execute("DELETE FROM main WHERE id_liste=$1", id_liste)
            await self.bot.con.execute("DELETE FROM tasks WHERE id_liste=$1", id_liste)

            await ctx.send("{} successfully deleted".format(liste))
            return
        await ctx.send("Only the creator of the liste can delete it.\n Enter: $leave [liste name] to leave a party liste")

    async def delete_task(self,id_task, id_liste, id_user):
        await self.bot.con.execute("DELETE FROM tasks WHERE id_task=$1", id_task)

        #find liste row and upading the liste's stats
        liste_row = await self.bot.con.fetchrow("SELECT * FROM listes WHERE id_liste=$1", id_liste)
        await self.bot.con.execute("UPDATE listes SET nb_tasks=$1 WHERE id_liste=$2", liste_row['nb_tasks']-1, id_liste)

        #find user row and upading the user's stats
        user = await self.bot.con.fetchrow("SELECT * FROM users WHERE id_user=$1", id_user)
        await self.bot.con.execute("UPDATE users SET nb_tasks=$1 WHERE id_user=$2", user['nb_tasks']-1, id_user)


        if liste_row['nb_tasks'] <= 1:
            await self.bot.con.execute("UPDATE main SET id_task=NULL, t_name=NULL WHERE id_liste=$1",id_liste)
            return

        await self.bot.con.execute("DELETE FROM main WHERE id_task=$1", id_task)

def setup(bot):
    bot.add_cog(ModificationCommands(bot))