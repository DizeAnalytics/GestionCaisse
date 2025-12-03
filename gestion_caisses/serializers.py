from rest_framework import serializers
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from .models import (
    Region, Prefecture, Commune, Canton, Village, Quartier,
    Caisse, Membre, Pret, Echeance, MouvementFond, 
    VirementBancaire, AuditLog, Notification, CaisseGenerale, CaisseGeneraleMouvement, TransfertCaisse,
    SeanceReunion, Cotisation, Depense, SalaireAgent, FichePaie, Agent,
    ExerciceCaisse
)


def serialize_exercice_info(exercice):
    """Retourne une représentation normalisée d'un exercice."""
    if not exercice:
        return None

    today = timezone.now().date()

    # Recalcule est_actif à partir de la date et du statut pour être sûr
    statut = exercice.statut
    date_fin_modele = exercice.date_fin
    if date_fin_modele is None and exercice.date_debut:
        # Durée standard: 12 mois, cohérent avec le modèle
        date_fin_modele = exercice.date_debut + timedelta(days=365)

    est_actif = (
        statut == 'EN_COURS'
        and exercice.date_debut is not None
        and (date_fin_modele is None or today <= date_fin_modele)
    )

    if statut == 'EN_COURS' and not est_actif:
        statut = 'CLOTURE'

    date_fin = date_fin_modele

    return {
        'id': exercice.id,
        'date_debut': exercice.date_debut,
        'date_fin': date_fin,
        'statut': statut,
        'est_actif': est_actif,
    }


class UserSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les utilisateurs Django"""
    role = serializers.SerializerMethodField()
    caisse_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser', 'date_joined', 'last_login', 'role', 'caisse_nom']
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_role(self, obj):
        """Détermine le rôle de l'utilisateur basé sur son profil membre"""
        try:
            membre = obj.profil_membre
            return membre.role
        except:
            if obj.is_superuser:
                return 'ADMIN'
            return 'MEMBRE'
    
    def get_caisse_nom(self, obj):
        """Récupère le nom de la caisse de l'utilisateur"""
        try:
            membre = obj.profil_membre
            return membre.caisse.nom_association if membre.caisse else None
        except:
            return None


class AgentListSerializer(serializers.ModelSerializer):
    """Sérialiseur léger pour lister les agents"""
    nom_complet = serializers.ReadOnlyField()

    class Meta:
        model = Agent
        fields = ['id', 'nom_complet', 'matricule', 'statut']


class RegionSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les régions"""
    class Meta:
        model = Region
        fields = '__all__'


class PrefectureSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les préfectures"""
    region = RegionSerializer(read_only=True)
    region_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Prefecture
        fields = '__all__'


class CommuneSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les communes"""
    prefecture = PrefectureSerializer(read_only=True)
    prefecture_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Commune
        fields = '__all__'


class CantonSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les cantons"""
    commune = CommuneSerializer(read_only=True)
    commune_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Canton
        fields = '__all__'


class VillageSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les villages"""
    canton = CantonSerializer(read_only=True)
    canton_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Village
        fields = '__all__'


class QuartierSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les quartiers"""
    village = VillageSerializer(read_only=True)
    village_id = serializers.IntegerField(write_only=True)
    canton_nom = serializers.CharField(source='village.canton.nom', read_only=True)
    commune_nom = serializers.CharField(source='village.canton.commune.nom', read_only=True)
    prefecture_nom = serializers.CharField(source='village.canton.commune.prefecture.nom', read_only=True)
    region_nom = serializers.CharField(source='village.canton.commune.prefecture.region.nom', read_only=True)

    class Meta:
        model = Quartier
        fields = '__all__'


class MembreSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les membres"""
    nom_complet = serializers.ReadOnlyField()
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    caisse_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    quartier = QuartierSerializer(read_only=True)
    quartier_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Membre
        fields = '__all__'
        extra_kwargs = {
            'photo': {'required': False},
            'date_adhesion': {'read_only': True},
            'date_derniere_activite': {'read_only': True},
            'caisse': {'read_only': True},
        }


class CaisseSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les caisses"""
    region = RegionSerializer(read_only=True)
    prefecture = PrefectureSerializer(read_only=True)
    commune = CommuneSerializer(read_only=True)
    canton = CantonSerializer(read_only=True)
    village = VillageSerializer(read_only=True)
    
    # IDs pour la création/modification
    region_id = serializers.IntegerField(write_only=True)
    prefecture_id = serializers.IntegerField(write_only=True)
    commune_id = serializers.IntegerField(write_only=True)
    canton_id = serializers.IntegerField(write_only=True)
    village_id = serializers.IntegerField(write_only=True)
    
    # Champs calculés
    nombre_membres = serializers.ReadOnlyField()
    nombre_prets_actifs = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    # Membres dirigeants
    presidente = MembreSerializer(read_only=True)
    secretaire = MembreSerializer(read_only=True)
    tresoriere = MembreSerializer(read_only=True)
    
    # Noms des responsables pour faciliter l'affichage
    presidente_nom = serializers.CharField(source='presidente.nom_complet', read_only=True)
    secretaire_nom = serializers.CharField(source='secretaire.nom_complet', read_only=True)
    tresoriere_nom = serializers.CharField(source='tresoriere.nom_complet', read_only=True)
    presidente_telephone = serializers.CharField(source='presidente.numero_telephone', read_only=True)
    secretaire_telephone = serializers.CharField(source='secretaire.numero_telephone', read_only=True)
    tresoriere_telephone = serializers.CharField(source='tresoriere.numero_telephone', read_only=True)
    
    # Agent responsable
    agent_nom = serializers.CharField(source='agent.nom_complet', read_only=True)
    
    # Localisation
    village_nom = serializers.CharField(source='village.nom', read_only=True)
    canton_nom = serializers.CharField(source='canton.nom', read_only=True)
    commune_nom = serializers.CharField(source='commune.nom', read_only=True)
    prefecture_nom = serializers.CharField(source='prefecture.nom', read_only=True)
    region_nom = serializers.CharField(source='region.nom', read_only=True)
    
    # Localisation complète pour l'affichage
    localisation = serializers.SerializerMethodField()
    
    # Exercice en cours
    exercice_actuel = serializers.SerializerMethodField()
    
    presidente_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    secretaire_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    tresoriere_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    def get_localisation(self, obj):
        """Construit la localisation complète"""
        parts = []
        if obj.village:
            parts.append(obj.village.nom)
        if obj.canton:
            parts.append(obj.canton.nom)
        if obj.commune:
            parts.append(obj.commune.nom)
        return ', '.join(parts) if parts else 'Non définie'
    
    def get_exercice_actuel(self, obj):
        """Récupère l'exercice en cours ou le dernier exercice clôturé"""
        # Priorité: exercice EN_COURS, sinon le dernier exercice (le plus récent)
        exercice = obj.exercices.filter(statut='EN_COURS').order_by('-date_debut').first()
        if exercice:
            return serialize_exercice_info(exercice)

        # Si aucun exercice en cours, prendre le dernier exercice (même clôturé)
        exercice = obj.exercices.order_by('-date_debut', '-date_creation').first()
        return serialize_exercice_info(exercice)
    
    class Meta:
        model = Caisse
        fields = '__all__'
        extra_kwargs = {
            'code': {'read_only': True},
            'date_creation': {'read_only': True},
            'fond_disponible': {'read_only': True},
            'montant_total_prets': {'read_only': True},
            'montant_total_remboursements': {'read_only': True},
        }


class ExerciceCaisseSerializer(serializers.ModelSerializer):
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)

    class Meta:
        model = ExerciceCaisse
        fields = '__all__'
        read_only_fields = ['date_creation', 'date_modification']


class EcheanceSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les échéances"""
    pret_numero = serializers.CharField(source='pret.numero_pret', read_only=True)
    
    class Meta:
        model = Echeance
        fields = '__all__'
        extra_kwargs = {
            'date_paiement': {'required': False},
        }


class PretSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les prêts"""
    membre = MembreSerializer(read_only=True)
    caisse = CaisseSerializer(read_only=True)
    membre_id = serializers.IntegerField(write_only=True)
    caisse_id = serializers.IntegerField(write_only=True)
    interet_total = serializers.SerializerMethodField()
    interet_mensuel = serializers.SerializerMethodField()
    
    # Champs calculés
    montant_restant = serializers.ReadOnlyField()
    total_a_rembourser = serializers.ReadOnlyField()
    est_en_retard = serializers.ReadOnlyField()
    
    # Échéances
    echeances = EcheanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Pret
        fields = '__all__'
        extra_kwargs = {
            'numero_pret': {'read_only': True},
            'date_demande': {'read_only': True},
            'date_validation': {'required': False},
            'date_decaissement': {'required': False},
            'date_fin_pret': {'read_only': True},
            'date_remboursement_complet': {'required': False},
            'montant_rembourse': {'read_only': True},
            'nombre_echeances': {'read_only': True},
            'nombre_echeances_payees': {'read_only': True},
        }
    
    def validate(self, data):
        """Validation personnalisée pour les prêts"""
        # Vérifier si c'est une création (nouveau prêt)
        if self.instance is None:
            membre_id = data.get('membre_id')
            caisse_id = data.get('caisse_id')
            montant_demande = data.get('montant_demande')
            if membre_id:
                # Vérifier si le membre a déjà un prêt en cours
                from .models import Pret, Membre
                prets_ouverts = Pret.objects.filter(
                    membre_id=membre_id,
                    statut__in=['EN_ATTENTE', 'EN_ATTENTE_ADMIN', 'VALIDE', 'EN_COURS', 'EN_RETARD', 'BLOQUE']
                )
                if prets_ouverts.exists():
                    pret_existant = prets_ouverts.first()
                    raise serializers.ValidationError({
                        'membre': f"Le membre sélectionné a déjà un prêt en cours (statut: {pret_existant.get_statut_display()}). "
                                  "Il doit clôturer ce prêt avant d'en créer un nouveau. "
                                  "Les prêts remboursés permettent de faire un nouveau prêt."
                    })
                # Règle d'éligibilité: au moins 3 mois cotisés OU total cotisations >= 5000 FCFA
                try:
                    membre = Membre.objects.get(id=membre_id)
                    mois_ok = getattr(membre, 'est_eligible_pret_selon_cotisations', None)
                    mois_ok = mois_ok(minimum_mois=3) if callable(mois_ok) else False
                    total_cot_fn = getattr(membre, 'total_cotisations', None)
                    total_cot = total_cot_fn() if callable(total_cot_fn) else 0
                    # Plafond: 2x total cotisations
                    if montant_demande is not None:
                        try:
                            plafond = (total_cot or 0) * 2
                            if float(montant_demande) > float(plafond):
                                raise serializers.ValidationError({
                                    'montant_demande': f"Le montant demandé dépasse le plafond autorisé ({plafond:,.0f} FCFA = 2x cotisations cumulées)."
                                })
                        except Exception:
                            pass
                    if not (mois_ok or (total_cot >= 5000)):
                        raise serializers.ValidationError({
                            'membre': "Éligibilité refusée: il faut avoir cotisé pendant au moins 3 mois ou un total minimum de 5000 FCFA."
                        })
                    if caisse_id and membre.caisse_id != caisse_id:
                        raise serializers.ValidationError({'caisse': "Le membre doit appartenir à la caisse sélectionnée."})
                except Membre.DoesNotExist:
                    raise serializers.ValidationError({'membre': 'Membre introuvable.'})
        
        return data

    def get_interet_total(self, obj):
        try:
            return obj.montant_interet_calcule
        except Exception:
            return 0

    def get_interet_mensuel(self, obj):
        try:
            return obj.montant_interet_mensuel
        except Exception:
            return 0


class MouvementFondSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les mouvements de fonds"""
    caisse = CaisseSerializer(read_only=True)
    pret = PretSerializer(read_only=True)
    utilisateur = UserSerializer(read_only=True)
    
    caisse_id = serializers.IntegerField(write_only=True)
    pret_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = MouvementFond
        fields = '__all__'
        extra_kwargs = {
            'date_mouvement': {'read_only': True},
            'solde_avant': {'read_only': True},
            'solde_apres': {'read_only': True},
        }


class VirementBancaireSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les virements bancaires"""
    caisse = CaisseSerializer(read_only=True)
    caisse_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = VirementBancaire
        fields = '__all__'
        extra_kwargs = {
            'date_demande': {'read_only': True},
            'date_execution': {'required': False},
            'reference_bancaire': {'required': False},
        }


class CaisseGeneraleSerializer(serializers.ModelSerializer):
    solde_systeme = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = CaisseGenerale
        fields = ['id', 'nom', 'solde_reserve', 'solde_total_caisses', 'solde_systeme', 'actif', 'date_mise_a_jour']


class CaisseGeneraleMouvementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaisseGeneraleMouvement
        fields = '__all__'
    
    def validate(self, data):
        """Validation personnalisée pour les mouvements de caisse générale"""
        from .models import CaisseGenerale
        
        # Vérifier que le montant est positif
        if data.get('montant', 0) <= 0:
            raise serializers.ValidationError("Le montant doit être strictement positif.")
        
        # Pour les alimentations de caisses, vérifier que la caisse générale a suffisamment de fonds
        if data.get('type_mouvement') == 'ALIMENTATION_CAISSE':
            if not data.get('caisse_destination'):
                raise serializers.ValidationError("Une caisse de destination est requise pour l'alimentation d'une caisse.")
            
            # Vérifier que la caisse générale a suffisamment de fonds
            caisse_generale = CaisseGenerale.get_instance()
            montant_demande = data.get('montant', 0)
            
            if caisse_generale.solde_reserve < montant_demande:
                raise serializers.ValidationError({
                    'montant': f"Fonds insuffisants. La caisse générale dispose de {caisse_generale.solde_reserve} FCFA, "
                              f"mais {montant_demande} FCFA sont demandés. "
                              f"Solde disponible: {caisse_generale.solde_reserve} FCFA"
                })
        
        # Pour les sorties, vérifier également que la caisse générale a suffisamment de fonds
        elif data.get('type_mouvement') == 'SORTIE':
            caisse_generale = CaisseGenerale.get_instance()
            montant_demande = data.get('montant', 0)
            
            if caisse_generale.solde_reserve < montant_demande:
                raise serializers.ValidationError({
                    'montant': f"Fonds insuffisants. La caisse générale dispose de {caisse_generale.solde_reserve} FCFA, "
                              f"mais {montant_demande} FCFA sont demandés. "
                              f"Solde disponible: {caisse_generale.solde_reserve} FCFA"
                })
        
        return data


class TransfertCaisseSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les transferts entre caisses"""
    caisse_source = CaisseSerializer(read_only=True)
    caisse_destination = CaisseSerializer(read_only=True)
    utilisateur = UserSerializer(read_only=True)
    mouvement_source = MouvementFondSerializer(read_only=True)
    mouvement_destination = MouvementFondSerializer(read_only=True)
    
    # IDs pour la création/modification
    # La source est requise pour 'CAISSE_VERS_CAISSE' et 'CAISSE_VERS_GENERALE' mais pas pour 'GENERALE_VERS_CAISSE'
    caisse_source_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    caisse_destination_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = TransfertCaisse
        fields = '__all__'
        extra_kwargs = {
            'date_transfert': {'read_only': True},
            'statut': {'read_only': True},
            'mouvement_source': {'read_only': True},
            'mouvement_destination': {'read_only': True},
            'utilisateur': {'read_only': True},
        }
    
    def validate(self, data):
        """Validation personnalisée pour les transferts"""
        from .models import Caisse, CaisseGenerale
        
        # Vérifier que le montant est positif
        if data.get('montant', 0) <= 0:
            raise serializers.ValidationError("Le montant doit être strictement positif.")
        
        type_transfert = data.get('type_transfert')
        caisse_source_id = data.get('caisse_source_id')
        caisse_destination_id = data.get('caisse_destination_id')
        
        # Validation selon le type de transfert
        if type_transfert == 'CAISSE_VERS_CAISSE':
            if not caisse_source_id:
                raise serializers.ValidationError("Une caisse source est requise pour un transfert entre caisses.")
            if not caisse_destination_id:
                raise serializers.ValidationError("Une caisse de destination est requise pour un transfert entre caisses.")
            
            if caisse_source_id == caisse_destination_id:
                raise serializers.ValidationError("Une caisse ne peut pas se transférer de l'argent à elle-même.")
            
            # Vérifier que la caisse source a suffisamment de fonds
            try:
                caisse_source = Caisse.objects.get(id=caisse_source_id)
                montant_demande = data.get('montant', 0)
                
                if caisse_source.fond_disponible < montant_demande:
                    raise serializers.ValidationError({
                        'montant': f"Fonds insuffisants. La caisse {caisse_source.nom_association} dispose de {caisse_source.fond_disponible} FCFA, "
                                  f"mais {montant_demande} FCFA sont demandés pour le transfert."
                    })
            except Caisse.DoesNotExist:
                raise serializers.ValidationError("Caisse source introuvable.")
        
        elif type_transfert == 'CAISSE_VERS_GENERALE':
            if not caisse_source_id:
                raise serializers.ValidationError("Une caisse source est requise pour un transfert vers la caisse générale.")
            # Vérifier que la caisse source a suffisamment de fonds
            try:
                caisse_source = Caisse.objects.get(id=caisse_source_id)
                montant_demande = data.get('montant', 0)
                
                if caisse_source.fond_disponible < montant_demande:
                    raise serializers.ValidationError({
                        'montant': f"Fonds insuffisants. La caisse {caisse_source.nom_association} dispose de {caisse_source.fond_disponible} FCFA, "
                                  f"mais {montant_demande} FCFA sont demandés pour le transfert vers la caisse générale."
                    })
            except Caisse.DoesNotExist:
                raise serializers.ValidationError("Caisse source introuvable.")
        
        elif type_transfert == 'GENERALE_VERS_CAISSE':
            if not caisse_destination_id:
                raise serializers.ValidationError("Une caisse de destination est requise pour un transfert de la caisse générale.")
            
            # Vérifier que la caisse générale a suffisamment de fonds
            caisse_generale = CaisseGenerale.get_instance()
            montant_demande = data.get('montant', 0)
            
            if caisse_generale.solde_reserve < montant_demande:
                raise serializers.ValidationError({
                    'montant': f"Fonds insuffisants. La caisse générale dispose de {caisse_generale.solde_reserve} FCFA, "
                              f"mais {montant_demande} FCFA sont demandés pour le transfert."
                })
        
        return data
    
    def create(self, validated_data):
        """Créer le transfert et l'exécuter automatiquement"""
        # Assigner l'utilisateur actuel
        validated_data['utilisateur'] = self.context['request'].user
        
        # Créer le transfert
        transfert = TransfertCaisse.objects.create(**validated_data)
        
        # Exécuter le transfert
        try:
            transfert.executer_transfert()
        except Exception as e:
            # En cas d'erreur, supprimer le transfert et lever l'exception
            transfert.delete()
            raise serializers.ValidationError(f"Erreur lors de l'exécution du transfert: {str(e)}")
        
        return transfert


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()
    
    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ['date_action']


class SeanceReunionSerializer(serializers.ModelSerializer):
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)

    class Meta:
        model = SeanceReunion
        fields = '__all__'


class CotisationSerializer(serializers.ModelSerializer):
    membre_nom = serializers.CharField(source='membre.nom_complet', read_only=True)
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    seance_date = serializers.DateField(source='seance.date_seance', read_only=True)

    membre_id = serializers.IntegerField(write_only=True)
    caisse_id = serializers.IntegerField(write_only=True)
    seance_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Cotisation
        fields = '__all__'
        extra_kwargs = {
            'date_cotisation': {'read_only': True},
            'montant_total': {'read_only': True},
            'utilisateur': {'read_only': True},
            # Utiliser les champs *_id en écriture, ne pas exiger les relations directes
            'membre': {'required': False, 'allow_null': True},
            'caisse': {'required': False, 'allow_null': True},
            'seance': {'required': False, 'allow_null': True},
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['utilisateur'] = request.user
        return super().create(validated_data)

    def validate(self, attrs):
        """Empêcher qu'un membre cotise deux fois pour la même séance."""
        from .models import Cotisation
        membre_id = attrs.get('membre_id') or getattr(self.instance, 'membre_id', None)
        seance_id = attrs.get('seance_id') or getattr(self.instance, 'seance_id', None)
        if membre_id and seance_id:
            qs = Cotisation.objects.filter(membre_id=membre_id, seance_id=seance_id)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({'membre': "Ce membre a déjà cotisé pour cette séance."})
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    destinataire = serializers.StringRelatedField()
    caisse = serializers.StringRelatedField()
    pret = serializers.StringRelatedField()
    
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['date_creation']


class NotificationListSerializer(serializers.ModelSerializer):
    destinataire = serializers.StringRelatedField()
    caisse = serializers.StringRelatedField()
    pret = serializers.StringRelatedField()
    pret_id = serializers.IntegerField(source='pret.id', read_only=True)
    pret_statut = serializers.CharField(source='pret.statut', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'destinataire', 'type_notification', 'titre', 'message', 'caisse', 'pret', 'pret_id', 'pret_statut',
            'statut', 'date_creation', 'lien_action'
        ]
        read_only_fields = ['date_creation']


# Sérialiseurs pour les listes et détails
class CaisseListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des caisses"""
    region_nom = serializers.CharField(source='region.nom', read_only=True)
    prefecture_nom = serializers.CharField(source='prefecture.nom', read_only=True)
    commune_nom = serializers.CharField(source='commune.nom', read_only=True)
    village_nom = serializers.CharField(source='village.nom', read_only=True)
    canton_nom = serializers.CharField(source='canton.nom', read_only=True)
    nombre_membres = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    # Agent responsable
    agent_nom = serializers.CharField(source='agent.nom_complet', read_only=True)
    
    # Noms des responsables pour faciliter l'affichage
    presidente_nom = serializers.CharField(source='presidente.nom_complet', read_only=True)
    secretaire_nom = serializers.CharField(source='secretaire.nom_complet', read_only=True)
    tresoriere_nom = serializers.CharField(source='tresoriere.nom_complet', read_only=True)
    presidente_telephone = serializers.CharField(source='presidente.numero_telephone', read_only=True)
    secretaire_telephone = serializers.CharField(source='secretaire.numero_telephone', read_only=True)
    tresoriere_telephone = serializers.CharField(source='tresoriere.numero_telephone', read_only=True)
    
    # Localisation complète pour l'affichage
    localisation = serializers.SerializerMethodField()
    
    # Exercice en cours
    exercice_actuel = serializers.SerializerMethodField()
    
    def get_localisation(self, obj):
        """Construit la localisation complète"""
        parts = []
        if obj.village:
            parts.append(obj.village.nom)
        if obj.canton:
            parts.append(obj.canton.nom)
        if obj.commune:
            parts.append(obj.commune.nom)
        return ', '.join(parts) if parts else 'Non définie'
    
    def get_exercice_actuel(self, obj):
        """Récupère l'exercice en cours ou le dernier exercice clôturé"""
        # Priorité: exercice EN_COURS, sinon le dernier exercice (le plus récent)
        exercice = obj.exercices.filter(statut='EN_COURS').order_by('-date_debut').first()
        if exercice:
            return serialize_exercice_info(exercice)

        # Si aucun exercice en cours, prendre le dernier exercice (même clôturé)
        exercice = obj.exercices.order_by('-date_debut', '-date_creation').first()
        return serialize_exercice_info(exercice)
    
    class Meta:
        model = Caisse
        fields = [
            'id', 'code', 'nom_association', 'region_nom', 'prefecture_nom', 
            'commune_nom', 'village_nom', 'canton_nom', 'statut', 'nombre_membres', 
            'fond_disponible', 'solde_disponible', 'date_creation', 'agent_nom',
            'presidente_nom', 'secretaire_nom', 'tresoriere_nom',
            'presidente_telephone', 'secretaire_telephone', 'tresoriere_telephone',
            'localisation', 'exercice_actuel'
        ]


class MembreListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des membres"""
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    nom_complet = serializers.ReadOnlyField()
    photo = serializers.ImageField(read_only=True)
    numero_telephone = serializers.CharField(read_only=True)
    
    class Meta:
        model = Membre
        fields = [
            'id', 'numero_carte_electeur', 'nom_complet', 'role', 'statut',
            'caisse_nom', 'date_adhesion', 'numero_telephone', 'photo'
        ]


class PretListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des prêts"""
    membre_nom = serializers.CharField(source='membre.nom_complet', read_only=True)
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    caisse_code = serializers.CharField(source='caisse.code', read_only=True)
    montant_restant = serializers.ReadOnlyField()
    total_a_rembourser = serializers.ReadOnlyField()
    taux_interet = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    interet_total = serializers.SerializerMethodField()
    interet_mensuel = serializers.SerializerMethodField()
    
    class Meta:
        model = Pret
        fields = [
            'id', 'numero_pret', 'membre_nom', 'caisse_nom', 'caisse_code', 'montant_demande',
            'montant_accord', 'statut', 'date_demande', 'montant_restant',
            'total_a_rembourser', 'taux_interet', 'interet_total', 'interet_mensuel'
        ]

    def get_interet_total(self, obj):
        try:
            return obj.montant_interet_calcule
        except Exception:
            return 0

    def get_interet_mensuel(self, obj):
        try:
            return obj.montant_interet_mensuel
        except Exception:
            return 0


# Sérialiseurs pour les statistiques et tableaux de bord
class CaisseStatsSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les statistiques des caisses"""
    nombre_membres = serializers.ReadOnlyField()
    nombre_prets_actifs = serializers.ReadOnlyField()
    montant_total_prets = serializers.ReadOnlyField()
    montant_total_remboursements = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    class Meta:
        model = Caisse
        fields = [
            'id', 'code', 'nom_association', 'statut', 'nombre_membres',
            'nombre_prets_actifs', 'fond_disponible', 'montant_total_prets',
            'montant_total_remboursements', 'solde_disponible'
        ]


class DashboardStatsSerializer(serializers.Serializer):
    total_caisses = serializers.IntegerField()
    total_membres = serializers.IntegerField()
    total_prets_actifs = serializers.IntegerField()
    montant_total_circulation = serializers.DecimalField(max_digits=15, decimal_places=2)
    solde_total_disponible = serializers.DecimalField(max_digits=15, decimal_places=2)
    caisses_par_region = serializers.ListField()
    evolution_prets = serializers.ListField()
    taux_remboursement = serializers.FloatField()
    notifications_non_lues = serializers.IntegerField()
    demandes_pret_en_attente = serializers.IntegerField()


class DepenseSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les dépenses (modèle simplifié)"""
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    responsable_nom = serializers.SerializerMethodField()
    categorie_display = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()
    statut_display = serializers.SerializerMethodField()

    class Meta:
        model = Depense
        fields = '__all__'
        read_only_fields = ['date_creation', 'date_modification', 'utilisateur']

    def get_responsable_nom(self, obj):
        user = getattr(obj, 'utilisateur', None)
        if not user:
            return 'Inconnu'
        return (user.get_full_name() or user.get_username() or 'Inconnu').strip()

    def get_categorie_display(self, obj):
        return obj.Objectifdepense or 'Sans objectif'

    def get_statut(self, obj):
        # Le modèle simplifié ne gère pas encore plusieurs statuts
        return 'ENREGISTREE'

    def get_statut_display(self, obj):
        return 'Enregistrée'


class DepenseListSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la liste des dépenses (modèle simplifié)"""
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)

    class Meta:
        model = Depense
        fields = [
            'id', 'caisse_nom', 'Objectifdepense', 'montantdepense', 'datedepense', 'observation', 'date_creation'
        ]


class SalaireAgentSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les salaires des agents"""
    agent_nom = serializers.CharField(source='agent.nom_complet', read_only=True)
    agent_matricule = serializers.CharField(source='agent.matricule', read_only=True)
    periode = serializers.ReadOnlyField()
    nombre_nouvelles_caisses = serializers.ReadOnlyField()
    
    class Meta:
        model = SalaireAgent
        fields = [
            'id', 'agent', 'agent_nom', 'agent_matricule', 'mois', 'annee',
            'salaire_base', 'bonus_caisses', 'prime_performance', 'total_brut',
            'deductions', 'total_net', 'statut', 'date_paiement', 'mode_paiement',
            'notes', 'periode', 'nombre_nouvelles_caisses', 'date_creation',
            'date_modification'
        ]
        read_only_fields = ['total_brut', 'total_net', 'date_creation', 'date_modification']
    
    def validate(self, data):
        """Validation personnalisée pour les salaires"""
        # Vérifier que le mois est entre 1 et 12
        mois = data.get('mois')
        if mois and (mois < 1 or mois > 12):
            raise serializers.ValidationError("Le mois doit être entre 1 et 12")
        
        # Vérifier que l'année est raisonnable
        annee = data.get('annee')
        if annee and (annee < 2000 or annee > 2100):
            raise serializers.ValidationError("L'année doit être entre 2000 et 2100")
        
        # Vérifier qu'il n'y a pas de doublon agent/mois/année
        agent = data.get('agent')
        mois = data.get('mois')
        annee = data.get('annee')
        
        if agent and mois and annee:
            existing = SalaireAgent.objects.filter(
                agent=agent, mois=mois, annee=annee
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    f"Un salaire existe déjà pour l'agent {agent.nom_complet} "
                    f"pour la période {mois}/{annee}"
                )
        
        return data


class SalaireAgentListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des salaires des agents"""
    agent_nom = serializers.CharField(source='agent.nom_complet', read_only=True)
    agent_matricule = serializers.CharField(source='agent.matricule', read_only=True)
    periode = serializers.ReadOnlyField()
    
    class Meta:
        model = SalaireAgent
        fields = [
            'id', 'agent_nom', 'agent_matricule', 'mois', 'annee', 'periode',
            'salaire_base', 'bonus_caisses', 'prime_performance', 'total_brut',
            'total_net', 'statut', 'date_paiement', 'date_creation'
        ]


class FichePaieSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les fiches de paie des agents"""
    agent_nom = serializers.CharField(source='salaire.agent.nom_complet', read_only=True)
    agent_matricule = serializers.CharField(source='salaire.agent.matricule', read_only=True)
    periode = serializers.ReadOnlyField()
    fichier_pdf_url = serializers.SerializerMethodField()
    
    class Meta:
        model = FichePaie
        fields = [
            'id', 'salaire', 'type_fiche', 'agent_nom', 'agent_matricule',
            'nom_agent', 'matricule', 'poste', 'salaire_base', 'bonus_caisses',
            'prime_performance', 'total_brut', 'deductions', 'total_net',
            'mois', 'annee', 'periode', 'nombre_nouvelles_caisses',
            'fichier_pdf', 'fichier_pdf_url', 'date_generation', 'genere_par',
            'date_creation'
        ]
        read_only_fields = [
            'nom_agent', 'matricule', 'poste', 'salaire_base', 'bonus_caisses',
            'prime_performance', 'total_brut', 'deductions', 'total_net',
            'mois', 'annee', 'nombre_nouvelles_caisses', 'date_creation'
        ]
    
    def get_fichier_pdf_url(self, obj):
        """Retourne l'URL du fichier PDF s'il existe"""
        if obj.fichier_pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier_pdf.url)
        return None


class FichePaieListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des fiches de paie"""
    agent_nom = serializers.CharField(source='salaire.agent.nom_complet', read_only=True)
    agent_matricule = serializers.CharField(source='salaire.agent.matricule', read_only=True)
    periode = serializers.ReadOnlyField()
    fichier_pdf_url = serializers.SerializerMethodField()
    
    class Meta:
        model = FichePaie
        fields = [
            'id', 'agent_nom', 'agent_matricule', 'type_fiche', 'periode',
            'salaire_base', 'bonus_caisses', 'prime_performance', 'total_brut',
            'total_net', 'nombre_nouvelles_caisses', 'fichier_pdf_url',
            'date_generation', 'date_creation'
        ]
    
    def get_fichier_pdf_url(self, obj):
        """Retourne l'URL du fichier PDF s'il existe"""
        if obj.fichier_pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier_pdf.url)
        return None


class AgentSalairesStatsSerializer(serializers.Serializer):
    """Sérialiseur pour les statistiques des salaires des agents"""
    annee_courante = serializers.IntegerField()
    total_agents = serializers.IntegerField()
    stats_mensuelles = serializers.ListField()
    top_agents_bonus = serializers.ListField()
